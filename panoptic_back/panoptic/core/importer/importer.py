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
    ImageProperty, DbCommit, UploadError, UploadConfirm, PropertyGroup


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
        self._data: ImportData | None = None
        self.exclude = []
        self.properties = []

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

        return UploadConfirm(key=self.file_key, col_to_property=self.col_to_prop, errors=errors)

    async def determine_mapping_stats(self, relative: bool = False, fusion: str = 'new') -> dict[str, int]:
        """
        Determines the final instance mapping (including new instances via fusion),
        stores the finalized self._row_to_ids, and returns statistics on the outcome.

        Returns: A dictionary containing 'missing_rows' and 'new_instances'.
        """
        if not self.file_key or not self.columns:
            raise ValueError("Headers must be parsed first with parse_headers.")

        # Initialize ImportData and new instance list
        self._data = ImportData()
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
        self._data.instances = new_instances

        # 4. Find Missing rows
        missing_rows = []
        for i in range(len(self._row_to_ids)):
            if not self._row_to_ids[i]:
                missing_rows.append(i)

        print(self._row_to_ids)
        print(missing_rows)


        return {
            "missing_rows": missing_rows,
            "new_instances": len(new_instances)
        }

    async def parse_data(self, exclude: list[int] | None = None, properties: dict[int, Property] | None = None):
        """
        Reads ONLY the necessary data columns from the CSV and builds the ImportData object.
        """
        if self._row_to_ids is None or not self.col_to_prop or not self.columns:
            raise ValueError("Headers and Rows must be parsed first with parse_headers and parse_rows.")

        data = self._data
        exclude = set(exclude) if exclude else set()

        # Determine which columns need to be read from the file
        col_to_import_prop: dict[int, Property] = {}
        cols_to_read: list[str] = []  # List of column names to pass to pl.read_csv()

        for i, prop in self.col_to_prop.items():
            if i not in exclude:
                # Use the property from overrides, or the one parsed from the header
                final_prop = properties.get(i, prop)
                col_to_import_prop[i] = final_prop
                cols_to_read.append(self.columns[i])  # The index i corresponds to the column index in self.columns

        # Read ONLY the required data columns (and the key column if needed for indexing, though not needed here)
        if not cols_to_read:
            return  # Nothing to import

        # We must read columns by name, NOT by index, as Polars is expecting names.
        df_data = await self._read_csv(columns=cols_to_read)
        if df_data is None:
            raise IOError("Could not read data columns from CSV file.")

        # Add new properties to the data object
        data.properties.extend([p for p in col_to_import_prop.values() if p.id < 0])

        to_import: list[ImportValues] = []

        # Iterate over columns to import (using the names from the read DataFrame)
        for col_name in cols_to_read:
            # Find the original index 'i' (1-based) for this column name
            try:
                col_i = self.columns.index(col_name)
            except ValueError:
                continue  # Should not happen if logic is correct

            prop = col_to_import_prop[col_i]

            ids: list[int] = []
            values: list[Any] = []
            csv_values = df_data[col_name].to_list()

            tag_map: dict[str, Tag] = {}
            if prop.type in {PropertyType.tag, PropertyType.multi_tags}:
                if prop.id > 0:
                    db_tags = await self.project.db.get_tags(prop.id)
                    tag_map = {t.value: t for t in db_tags}

            # Iterate over rows
            for row_i, value in enumerate(csv_values):
                instance_ids_for_row = self._row_to_ids[row_i]
                if not instance_ids_for_row:
                    continue

                parsed_value = parser[prop.type](value)
                if parsed_value is None:
                    continue

                if tag_map is not None:
                    if not parsed_value:
                        continue

                    parsed_value = [v.strip() for v in parsed_value]
                    for tag_name in parsed_value:
                        tag_name = tag_name.strip()
                        if tag_name not in tag_map:
                            new_tag = Tag(id=gen_tag_id(), property_id=prop.id, value=tag_name, parents=[],
                                          color=randint(0, 11))
                            tag_map[tag_name] = new_tag
                            data.tags.append(new_tag)

                    parsed_value = [tag_map[tag_name].id for tag_name in parsed_value]

                ids.extend(instance_ids_for_row)
                values.extend([parsed_value for _ in instance_ids_for_row])

            to_import.append(ImportValues(property_id=prop.id, instance_ids=ids, values=values))

        data.values = to_import
        self._data = data

    async def confirm_import(self) -> DbCommit:
        """
        Commits the parsed data to the database. (Identical to previous implementation)
        """
        if self._data is None:
            raise ValueError("Data must be parsed first with parse_data.")

        data = self._data
        instance_values: list[InstanceProperty] = []
        image_values: list[ImageProperty] = []

        properties = await self.project.db.get_properties()
        property_index = {p.id: p for p in [*data.properties, *properties]}
        instance_ids = {id_ for v in data.values for id_ in v.instance_ids}
        instances = await self.project.db.get_instances(ids=list(instance_ids))
        instance_index: dict[int, Instance] = {i.id: i for i in [*instances, *data.instances]}

        for import_values in data.values:
            prop_mode = property_index[import_values.property_id].mode
            for id_, value in zip(import_values.instance_ids, import_values.values):
                if prop_mode == PropertyMode.id:
                    instance_values.append(InstanceProperty(
                        property_id=import_values.property_id, instance_id=id_, value=value
                    ))
                else:
                    image_values.append(ImageProperty(
                        property_id=import_values.property_id, sha1=instance_index[id_].sha1, value=value
                    ))

        group = PropertyGroup(id=-1, name='Imported')
        for prop in data.properties:
            prop.property_group_id = group.id

        commit = DbCommit()
        commit.property_groups = [group]
        commit.instances = data.instances
        commit.properties = data.properties
        commit.tags = data.tags
        commit.instance_values = instance_values
        commit.image_values = image_values

        await self.project.db.apply_commit(commit)
        return commit