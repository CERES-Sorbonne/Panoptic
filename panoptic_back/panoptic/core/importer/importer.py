from __future__ import annotations

from dataclasses import dataclass, field, replace
from random import randint
from typing import TYPE_CHECKING

import pandas as pd

from panoptic.core.importer.parsing import parser
from panoptic.utils import RelativePathTrie

if TYPE_CHECKING:
    from panoptic.core.project.project import Project
from panoptic.models import PropertyType, PropertyMode, Tag, Property, Instance, InstanceProperty, \
    ImageProperty, DbCommit, UploadError, UploadConfirm


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
        self._df: pd.DataFrame | None = None
        self._data: ImportData | None = None

    async def upload_csv(self, file: str):
        errors: dict[int, UploadError] = {}
        col_to_prop: dict[int, Property] = {}

        try:
            file_data = pd.read_csv(file, delimiter=';', encoding='utf-8', keep_default_na=False, dtype=str)
        except pd.errors.ParserError:
            errors[0] = UploadError.invalid_csv
            return UploadConfirm(key="", col_to_property=col_to_prop, errors=errors)

        self._df = file_data

        columns = list(self._df.columns)
        file_key = extract_key(columns)

        if file_key is None:
            errors[0] = UploadError.no_key

        file_props = [parse_header(i, col_name, errors) for i, col_name in enumerate(columns[1:], start=1) if col_name]
        db_properties = await self.project.db.get_properties()

        for i, name, type_ in file_props:
            col_to_prop[i] = Property(id=-i, name=name, type=type_, mode=PropertyMode.id)

        # merge with db properties if possible
        for db_prop in db_properties:
            for prop in col_to_prop.values():
                if prop.name == db_prop.name and prop.type == db_prop.type:
                    prop.id = db_prop.id
                    prop.mode = db_prop.mode
        print(errors)
        return UploadConfirm(key=file_key, col_to_property=col_to_prop, errors=errors)

    async def parse_file(self, exclude: list[int] = None, properties: dict[int, Property] = None,
                         relative: bool = False, fusion: str = 'new'):
        data = ImportData()

        if exclude is None:
            exclude = []
        if properties is None:
            properties = {}

        columns = list(self._df.columns)
        file_key = columns[0]
        file_props = [parse_header(i + 1, col_name, {}) for i, col_name in enumerate(columns[1:]) if col_name]
        db_properties = await self.project.db.get_properties()
        col_to_prop: dict[int, Property] = {}

        exclude = set(exclude) if exclude else set()
        for i, name, type_ in file_props:
            if i not in exclude:
                if i in properties:
                    col_to_prop[i] = properties[i]
                else:
                    col_to_prop[i] = Property(id=-i, name=name, type=type_, mode=PropertyMode.id)

        if not any(p.mode == PropertyMode.id for p in col_to_prop.values()):
            fusion = 'first'

        # merge with db properties if possible
        for db_prop in db_properties:
            for prop in col_to_prop.values():
                if prop.name == db_prop.name and prop.type == db_prop.type:
                    prop.id = db_prop.id
                    prop.mode = db_prop.mode

        data.properties.extend([p for p in col_to_prop.values() if p.id < 0])

        row_to_ids: list[list[int]] = []
        instances = await self.project.db.get_instances()
        instance_index = {i.id: i for i in instances}

        if file_key == 'id':
            all_ids = await self.project.db.get_all_instances_ids()
            for id_ in self._df[file_key]:
                n_id = int(id_)
                if n_id in all_ids:
                    row_to_ids.append([id_])
                else:
                    row_to_ids.append([])

        if file_key == 'path':
            paths = self._df[file_key]
            trie = RelativePathTrie()
            trie.insert_paths(instances)
            for path in paths:
                if relative:
                    ids = trie.search_relative_path(path)
                else:
                    ids = trie.search_absolute_path(path)
                row_to_ids.append(ids)

            if fusion == 'first':
                for i in range(len(row_to_ids)):
                    row_to_ids[i] = [row_to_ids[i][0]] if row_to_ids[i] else []
            if fusion == 'last':
                for i in range(len(row_to_ids)):
                    row_to_ids[i] = [row_to_ids[i][-1]] if row_to_ids[i] else []
            if fusion == 'new':
                to_test = [vv for v in row_to_ids for vv in v]
                empty = await self.project.db.test_empty(to_test)
                used_id = set({})
                for i in range(len(row_to_ids)):
                    valid = [i for i in row_to_ids[i] if i in empty and i not in used_id]
                    if valid:
                        free = valid[0]
                        used_id.add(free)
                        row_to_ids[i] = [free]
                    elif row_to_ids[i]:
                        instance_clone = replace(instance_index[row_to_ids[i][0]])
                        instance_clone.id = gen_instance_id()
                        row_to_ids[i] = [instance_clone.id]
                        data.instances.append(instance_clone)

        to_import: list[ImportValues] = []
        for col_i, col in enumerate(columns[1:], start=1):
            if col_i in exclude:
                continue
            prop = col_to_prop[col_i]
            ids = []
            values = []
            csv_values = self._df[col]
            tag_map: dict[str, Tag] | None = None
            if prop.type == PropertyType.tag or prop.type == PropertyType.multi_tags:
                tag_map = {}
                if prop.id > 0:
                    db_tags = await self.project.db.get_tags(prop.id)
                    tag_map = {t.value: t for t in db_tags}

            for row_i, value in enumerate(csv_values):
                value = parser[prop.type](value)
                if value is None:
                    continue

                if tag_map is not None:
                    if not value:
                        continue
                    # remove trailing spaces
                    value = [v.strip() for v in value]
                    for tag_name in value:
                        tag_name = tag_name.strip()
                        if tag_name not in tag_map:
                            tag_map[tag_name] = Tag(id=gen_tag_id(), property_id=prop.id, value=tag_name, parents=[],
                                                    color=randint(0, 11))
                            data.tags.append(tag_map[tag_name])
                    value = [tag_map[tag_name].id for tag_name in value]
                ids.extend(i for i in row_to_ids[row_i])
                values.extend(v for v in [value for i in range(len(row_to_ids[row_i]))])
            to_import.append(ImportValues(property_id=prop.id, instance_ids=ids, values=values))
        data.values = to_import
        self._data = data

        missing = [(i, self._df[file_key][i]) for i, x in enumerate(row_to_ids) if not x]
        return missing

    async def confirm_import(self):
        return await self.project.importer.import_data(self._data)

    async def import_data(self, data: ImportData):

        instance_values: list[InstanceProperty] = []
        image_values: list[ImageProperty] = []

        properties = await self.project.db.get_properties()
        property_index = {p.id: p for p in [*data.properties, *properties]}
        instance_ids = {id_ for v in data.values for id_ in v.instance_ids}
        instances = await self.project.db.get_instances(ids=list(instance_ids))
        instance_index: dict[int, Instance] = {i.id: i for i in [*instances, *data.instances]}

        for import_values in data.values:
            for id_, value in zip(import_values.instance_ids, import_values.values):
                if property_index[import_values.property_id].mode == PropertyMode.id:
                    instance_values.append(InstanceProperty(property_id=import_values.property_id, instance_id=id_,
                                                            value=value))
                else:
                    image_values.append(ImageProperty(property_id=import_values.property_id,
                                                      sha1=instance_index[id_].sha1, value=value))

        commit = DbCommit()
        commit.instances = data.instances
        commit.properties = data.properties
        commit.tags = data.tags
        commit.instance_values = instance_values
        commit.image_values = image_values
        await self.project.db.apply_commit(commit)
        return commit
