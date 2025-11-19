from __future__ import annotations

from dataclasses import dataclass, field, replace
from random import randint
from typing import TYPE_CHECKING, Any

import polars as pl

from panoptic.core.importer.parsing import parser
from panoptic.utils import RelativePathTrie

if TYPE_CHECKING:
    from panoptic.core.project.project import Project
from panoptic.models import PropertyType, PropertyMode, Tag, Property, Instance, InstanceProperty, \
    ImageProperty, DbCommit, UploadError, UploadConfirm, PropertyGroup, ImportVerify


@dataclass
class ImportValues:
    property_id: int
    instance_ids: list = field(default_factory=list)
    values: list = field(default_factory=list)
    write_mode: str = field(default="set")


@dataclass
class ImportData:
    instances: list[Instance] = field(default_factory=list)
    properties: list[Property] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)
    values: list[ImportValues] = field(default_factory=list)


def clean_type(type_: PropertyType):
    valid = {
        PropertyType.string,
        PropertyType.number,
        PropertyType.tag,
        PropertyType.multi_tags,
        PropertyType.image_link,
        PropertyType.url,
        PropertyType.date,
        PropertyType.path,
        PropertyType.color,
        PropertyType.checkbox,
        PropertyType.id,
        PropertyType.sha1,
        PropertyType.ahash,
        PropertyType.width,
        PropertyType.height
    }
    if type_ not in valid:
        return PropertyType.string
    return type_


valid_types = ['text', 'number', 'tag', 'multi_tags', 'url', 'date', 'path', 'color', 'checkbox']


def parse_header(index: int, name: str, errors: dict):
    if '[' not in name:
        if name in valid_keys:
            errors[index] = UploadError.invalid_position
        else:
            errors[index] = UploadError.missing_bracket
        type_ = PropertyType.string
    else:
        name, remain = name.split('[')
        raw_type = remain.split(']')[0]
        if raw_type not in valid_types:
            errors[index] = UploadError.invalid_type
            type_ = PropertyType.string
        else:
            type_ = PropertyType(raw_type)
            type_ = clean_type(type_)
    return index, name, type_


__tag_id_counter = 0


def gen_tag_id():
    global __tag_id_counter
    __tag_id_counter -= 1
    return __tag_id_counter


__instance_id_counter = 0


def gen_instance_id():
    global __instance_id_counter
    __instance_id_counter -= 1
    return __instance_id_counter


valid_keys = ['id', 'path']


def extract_key(columns):
    key = columns[0]
    if key not in valid_keys:
        return None
    return key


class Importer:
    def __init__(self, project: Project):
        self.project = project
        self.file_path: str = ''
        self.columns: list[str] | None = None  # Stores all column names from the header
        self._row_to_ids: list[list[int]] = []
        self.file_key: str | None = None
        self.col_to_prop: dict[int, Property] = {}
        self._new_instances: list[Instance] = []
        self.exclude = []
        self.properties = {}

    async def _read_csv(self, columns: list[str] | None = None,
                        stop_after_n_rows: int | None = None) -> pl.DataFrame | None:
        """Helper to read the CSV file, reading only specified columns."""
        try:
            return pl.read_csv(
                self.file_path,
                separator=';',
                encoding='utf-8',
                null_values=[],
                infer_schema=False,
                n_rows=stop_after_n_rows,
                columns=columns
            )
        except pl.exceptions.PolarsError:
            return None

    async def parse_headers(self, file_path: str) -> UploadConfirm:
        """
        Reads only the header to detect the key column and properties.
        """
        self.clear()
        self.file_path = file_path
        errors: dict[int, UploadError] = {}

        # 1. Read ONLY the header (n_rows=0) to get column names
        df = await self._read_csv(stop_after_n_rows=0)

        if df is None:
            errors[0] = UploadError.invalid_csv
            return UploadConfirm(key="", col_to_property={}, errors=errors)

        self.columns = df.columns
        self.file_key = extract_key(self.columns)

        if self.file_key is None:
            errors[0] = UploadError.no_key

        # 2. Parse header into file properties
        file_props = [
            parse_header(i, col_name, errors)
            for i, col_name in enumerate(self.columns[1:], start=1)
            if col_name
        ]

        # 3. Load DB properties
        db_properties = await self.project.db.get_properties()

        # 4. Build col_to_prop from file headers
        for i, name, type_ in file_props:
            prop = Property(
                id=-i,
                name=name,
                type=type_,
                mode=PropertyMode.id
            )
            self.col_to_prop[i] = prop

        # 5. Merge with existing DB properties
        for db_prop in db_properties:
            for prop in self.col_to_prop.values():
                if prop.name == db_prop.name and prop.type == db_prop.type:
                    prop.id = db_prop.id
                    prop.mode = db_prop.mode

        self.properties = self.col_to_prop
        return UploadConfirm(key=self.file_key, col_to_property=self.col_to_prop, errors=errors)

    async def verify_mapping(self, relative: bool = False, fusion: str = 'new') -> ImportVerify:
        """
        Determines the final instance mapping (including new instances via fusion),
        stores the finalized self._row_to_ids, and returns statistics on the outcome.

        Returns: A dictionary containing 'missing_rows' and 'new_instances'.
        """
        if not self.file_key or not self.columns:
            raise ValueError("Headers must be parsed first with parse_headers.")

        # Initialize ImportData and new instance list
        new_instances: list[Instance] = []

        # 1. Read ONLY the key column data
        df = await self._read_csv(columns=[self.file_key])
        if df is None:
            raise IOError("Could not read the key column from CSV file.")

        key_column_data = df[self.file_key].to_list()

        # This list will hold the final, fused IDs (temporary or existing)
        self._row_to_ids: list[list[int]] = []

        # Fetch all instances for path/fusion logic
        instances = await self.project.db.get_instances()
        instance_index = {i.id: i for i in instances}

        # 2. Initial Mapping: Find ALL possible existing matches
        initial_mapping: list[list[int]] = []
        if self.file_key == 'id':
            all_ids = await self.project.db.get_all_instances_ids()
            for id_ in key_column_data:
                try:
                    n_id = int(id_)
                    initial_mapping.append([n_id] if n_id in all_ids else [])
                except (ValueError, TypeError):
                    initial_mapping.append([])

        elif self.file_key == 'path':
            trie = RelativePathTrie()
            trie.insert_paths(instances)

            for path in key_column_data:
                if relative:
                    ids = trie.search_relative_path(path)
                else:
                    ids = trie.search_absolute_path(path)
                initial_mapping.append(ids)

        # 3. Apply Fusion Logic and Assign IDs (Including Negative IDs)

        current_mapping = initial_mapping  # Start with all matches
        empty = set()
        used_id = set()
        if fusion == 'new':
            to_test = [vv for v in current_mapping for vv in v]
            empty = await self.project.db.test_empty(to_test)
            used_id = set()

        for i in range(len(current_mapping)):
            if fusion == 'first':
                self._row_to_ids.append([current_mapping[i][0]] if current_mapping[i] else [])
            elif fusion == 'last':
                self._row_to_ids.append([current_mapping[i][-1]] if current_mapping[i] else [])
            elif fusion == 'new':
                if current_mapping[i]:
                    valid = [
                        inst_id for inst_id in current_mapping[i]
                        if inst_id in empty and inst_id not in used_id
                    ]
                    if valid:
                        # Found a reusable, empty instance
                        free_id = valid[0]
                        used_id.add(free_id)
                        self._row_to_ids.append([free_id])
                    elif self.file_key == 'path':
                        # Clone existing instance and assign a new temporary ID
                        instance_clone = replace(instance_index[current_mapping[i][0]])
                        instance_clone.id = gen_instance_id()
                        self._row_to_ids.append([instance_clone.id])
                        new_instances.append(instance_clone)
                    else:
                        # 'id' key fusion: Matched non-empty/non-reusable instance. No value assignment.
                        self._row_to_ids.append([])
                else:
                    self._row_to_ids.append([])  # No match
            else:
                # Default behavior (e.g., if fusion mode is not supported for key type)
                self._row_to_ids.append([current_mapping[i][0]] if current_mapping[i] else [])

        # Save new instances to data object
        self._new_instances = new_instances

        # 4. Find Missing rows
        missing_rows = []
        for i in range(len(self._row_to_ids)):
            if not self._row_to_ids[i]:
                missing_rows.append(i)

        return ImportVerify(missing_rows=missing_rows, new_instances_count=len(new_instances))


    async def import_data_and_commit(self, exclude: list[int] | None = None,
                                     properties: dict[int, Property] | None = None):
        """
        Executes the import process in sequential database commits.

        Optimized approach:
        1. Single-pass loop over data columns (load & clear).
        2. Creates Tags "just-in-time".
        3. Unified Batching: Sends new Tags AND Values in the same commit.
           The backend resolves the temporary negative IDs within the commit.
        4. Updates local cache with permanent Tag IDs after every batch.
        """
        if self._row_to_ids is None or not self.col_to_prop or not self.columns:
            raise ValueError("Mapping must be determined first.")

        if not properties:
            properties = self.properties

        # Configuration
        BATCH_SIZE = 25_000
        exclude = set(exclude) if exclude else set()

        # Mappings (Temp ID -> Permanent ID)
        temp_prop_id_map: dict[int, int] = {}
        temp_instance_id_map: dict[int, int] = {}

        # executed_commits: list[DbCommit] = []

        # --- 1. PREPARE COLUMN MAPPING ---

        col_to_import_prop: dict[int, Property] = {}
        cols_to_read: list[str] = []

        for i, prop in self.col_to_prop.items():
            if i not in exclude:
                final_prop = properties.get(i, prop)
                col_to_import_prop[i] = final_prop
                cols_to_read.append(self.columns[i])

        if not cols_to_read:
            return

        # --- 2. COMMIT NEW PROPERTIES ---

        new_properties = [p for p in col_to_import_prop.values() if p.id < 0]
        if new_properties:
            old_prop_ids = [p.id for p in new_properties]
            prop_commit = DbCommit(properties=new_properties)

            group = PropertyGroup(id=-1, name='Imported Data')
            prop_commit.property_groups = [group]
            for prop in new_properties:
                prop.property_group_id = group.id

            await self.project.db.apply_commit(prop_commit)
            # executed_commits.append(prop_commit)

            new_prop_ids = [p.id for p in prop_commit.properties]
            temp_prop_id_map = {old_id: new_id for old_id, new_id in zip(old_prop_ids, new_prop_ids)}

        # Update working properties with permanent IDs
        for prop in col_to_import_prop.values():
            if prop.id in temp_prop_id_map:
                prop.id = temp_prop_id_map[prop.id]

        # --- 3. COMMIT NEW INSTANCES ---

        if self._new_instances:
            old_instance_ids = [i.id for i in self._new_instances]
            instance_commit = DbCommit(instances=self._new_instances)
            await self.project.db.apply_commit(instance_commit)
            # executed_commits.append(instance_commit)

            new_instance_ids = [i.id for i in instance_commit.instances]
            temp_instance_id_map = {old_id: new_id for old_id, new_id in zip(old_instance_ids, new_instance_ids)}

        # --- 4. MAIN DATA IMPORT LOOP ---

        # State containers for the loop
        pending_tags: list[Tag] = []
        # Map to ensure we don't create the same temp tag twice inside one batch
        pending_tag_map: dict[tuple[int, str], int] = {}  # (prop_id, name) -> temp_id

        pending_instance_values: list[InstanceProperty] = []
        pending_image_values: list[ImageProperty] = []

        # Cache existing DB tags (Permanent IDs)
        # Structure: { prop_id: { tag_name: tag_id } }
        tag_lookup_cache: dict[int, dict[str, int]] = {}

        # Pre-fill cache for existing properties
        for prop in col_to_import_prop.values():
            if prop.type in {PropertyType.tag, PropertyType.multi_tags} and prop.id > 0:
                db_tags = await self.project.db.get_tags(prop.id)
                tag_lookup_cache[prop.id] = {t.value: t.id for t in db_tags}

        # Helper: SHA1 Map
        all_instances_sha1_map: dict[int, str] = {}
        if any(p.mode != PropertyMode.id for p in col_to_import_prop.values()):
            all_db_instances = await self.project.db.get_instances()
            all_instances_sha1_map = {i.id: i.sha1 for i in all_db_instances}

        # --- INTERNAL FLUSH FUNCTION ---
        async def flush_batch():
            """
            Sends Tags and Values in a single commit.
            Updates the tag_lookup_cache with the newly created permanent IDs.
            """
            nonlocal pending_tags, pending_instance_values, pending_image_values

            if not (pending_tags or pending_instance_values or pending_image_values):
                return

            # 1. Create Unified Commit
            # Backend automatically maps negative tag IDs in 'values' to the new tags in 'tags'
            commit = DbCommit(
                tags=list(pending_tags),
                instance_values=list(pending_instance_values),
                image_values=list(pending_image_values)
            )

            # 2. Apply Commit
            await self.project.db.apply_commit(commit)
            # executed_commits.append(commit)

            # 3. Post-Commit: Update Cache with Real IDs
            # We must iterate the committed tags to get their new permanent IDs
            # so future batches (and iterations) use the real ID.
            if commit.tags:
                # commit.tags contains the updated objects with positive IDs
                for tag_obj in commit.tags:
                    if tag_obj.property_id not in tag_lookup_cache:
                        tag_lookup_cache[tag_obj.property_id] = {}

                    # Map Name -> New Permanent ID
                    tag_lookup_cache[tag_obj.property_id][tag_obj.value] = tag_obj.id

            # 4. Clear buffers
            pending_tags.clear()
            pending_tag_map.clear()
            pending_instance_values.clear()
            pending_image_values.clear()

        # --- ITERATE COLUMNS ---
        for col_name in cols_to_read:
            col_i = self.columns.index(col_name)
            prop = col_to_import_prop[col_i]
            is_tag_prop = prop.type in {PropertyType.tag, PropertyType.multi_tags}

            # Load ONE column
            df_col = await self._read_csv(columns=[col_name])
            if df_col is None:
                continue

            csv_values = df_col[col_name].to_list()

            # Iterate Rows
            for row_i, value in enumerate(csv_values):
                instance_ids_for_row = self._row_to_ids[row_i]
                if not instance_ids_for_row:
                    continue

                parsed_value = parser[prop.type](value)
                if parsed_value is None:
                    continue

                final_value = parsed_value

                # --- TAG HANDLING ---
                if is_tag_prop:
                    if not parsed_value:
                        continue

                    parsed_names = [v.strip() for v in parser[prop.type](value)]
                    tag_ids = []

                    for name in parsed_names:
                        # 1. Check Permanent Cache (Already in DB or committed in prev batch)
                        if prop.id in tag_lookup_cache and name in tag_lookup_cache[prop.id]:
                            tag_ids.append(tag_lookup_cache[prop.id][name])

                        # 2. Check Pending Queue (Created in this current batch)
                        elif (prop.id, name) in pending_tag_map:
                            tag_ids.append(pending_tag_map[(prop.id, name)])

                        # 3. Create New Tag (Assign Temp ID)
                        else:
                            new_temp_id = gen_tag_id()
                            new_tag = Tag(
                                id=new_temp_id,
                                property_id=prop.id,
                                value=name,
                                parents=[],
                                color=randint(0, 11)
                            )

                            pending_tags.append(new_tag)
                            pending_tag_map[(prop.id, name)] = new_temp_id
                            tag_ids.append(new_temp_id)

                    final_value = tag_ids

                # --- CREATE VALUE OBJECTS ---

                # Map Instance IDs (Temp -> Perm)
                final_instance_ids = [
                    temp_instance_id_map.get(id_, id_) for id_ in instance_ids_for_row
                ]

                for instance_id in final_instance_ids:
                    if prop.mode == PropertyMode.id:
                        pending_instance_values.append(InstanceProperty(
                            property_id=prop.id, instance_id=instance_id, value=final_value
                        ))
                    else:
                        instance_sha1 = all_instances_sha1_map.get(instance_id)
                        if instance_sha1:
                            pending_image_values.append(ImageProperty(
                                property_id=prop.id, sha1=instance_sha1, value=final_value
                            ))

                # --- BATCH CHECK ---
                if len(pending_instance_values) + len(pending_image_values) >= BATCH_SIZE:
                    await flush_batch()

            # Clear memory immediately
            del df_col

        # Final Flush
        await flush_batch()
        self.clear()

    def clear(self):
        self._new_instances = []
        self._row_to_ids = None
        self.col_to_prop = {}
        self.columns = []
        self.properties = []