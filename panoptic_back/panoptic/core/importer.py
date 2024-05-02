from __future__ import annotations

from dataclasses import dataclass, field, replace
from random import randint
from typing import TYPE_CHECKING

import pandas as pd
from fastapi import UploadFile

from panoptic.utils import Trie, chunk_list

if TYPE_CHECKING:
    from panoptic.core.project.project import Project
from panoptic.models import PropertyType, PropertyMode, Tag, Property, Instance


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


def parse_list(value: str):
    if value is None or value == '' or pd.isnull(value):
        return None
    # value = value.replace('[', '')
    # value = value.replace(']', '')
    return value.split(',')


def parse_header(index: int, name: str):
    name, remain = name.split('[')
    type_ = PropertyType(remain.split(']')[0])
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


class Importer:
    def __init__(self, project: Project):
        self.project = project
        self._df: pd.DataFrame | None = None
        self._data: ImportData | None = None

    async def upload_csv(self, file: UploadFile):
        file_data = pd.read_csv(file.file, delimiter=';', encoding='utf-8', keep_default_na=False)
        self._df = file_data

        columns = list(self._df.columns)
        file_key = columns[0]
        file_props = [parse_header(i, col_name) for i, col_name in enumerate(columns[1:], start=1) if col_name]
        db_properties = await self.project.db.get_properties(no_computed=True)
        col_to_prop: dict[int, Property] = {}

        for i, name, type_ in file_props:
            col_to_prop[i] = Property(id=-i, name=name, type=type_, mode=PropertyMode.id)

        # merge with db properties if possible
        for db_prop in db_properties:
            for prop in col_to_prop.values():
                if prop.name == db_prop.name and prop.type == db_prop.type:
                    prop.id = db_prop.id
                    prop.mode = db_prop.mode

        return file_key, col_to_prop

    async def parse_file(self, exclude: list[int] = None, properties: dict[int, Property] = None,
                         relative: bool = False, fusion: str = 'new'):
        data = ImportData()

        columns = list(self._df.columns)
        file_key = columns[0]
        file_props = [parse_header(i + 1, col_name) for i, col_name in enumerate(columns[1:]) if col_name]
        db_properties = await self.project.db.get_properties(no_computed=True)
        col_to_prop: dict[int, Property] = {}

        exclude = set(exclude) if exclude else set()
        for i, name, type_ in file_props:
            if i not in exclude:
                if i in properties:
                    col_to_prop[i] = properties[i]
                else:
                    col_to_prop[i] = Property(id=-i, name=name, type=type_, mode=PropertyMode.id)

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
            for id_ in self._df[file_key]:
                row_to_ids.append([id_])
        if file_key == 'path':
            pass
            paths = self._df[file_key]
            trie = Trie()
            for inst in instances:
                trie.insert(inst.url[::-1], inst.id)
            for path in paths:
                if relative:
                    ids = trie.search_by_prefix(path[::-1])
                else:
                    ids = trie.search_by_word(path[::-1])
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
                for i in range(len(row_to_ids)):
                    valid = [i for i in row_to_ids[i] if i in empty]
                    if valid:
                        row_to_ids[i] = valid
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
                if value is None:
                    continue

                if tag_map is not None:
                    value = parse_list(value)
                    for tag_name in value:
                        if tag_name not in tag_map:
                            tag_map[tag_name] = Tag(id=gen_tag_id(), property_id=prop.id, value=tag_name, parents=[0],
                                                    color=randint(0, 11))
                            data.tags.append(tag_map[tag_name])
                    value = [tag_map[tag_name].id for tag_name in value]
                ids.extend(i for i in row_to_ids[row_i])
                values.extend(v for v in [value] * len(row_to_ids[row_i]))
            to_import.append(ImportValues(property_id=prop.id, instance_ids=ids, values=values))
        data.values = to_import
        #
        # print(f"Add {len(data.properties)} properties")
        # print(data.properties)
        #
        # print(f"Add {len(data.tags)} tags")
        # print(data.tags)
        #
        # print(f"Add {sum([len(v.values) for v in data.values], 0)} values")

        self._data = data

    async def confirm_import(self):
        await self.project.importer.import_data(self._data)

    async def import_data(self, data: ImportData):
        instance_fake_id_map: dict[int, Instance] = {}
        property_fake_id_map: dict[int, Property] = {}
        tag_fake_id_map: dict[int, Tag] = {}

        def correct_instance_id(id_: int):
            return id_ if id_ not in instance_fake_id_map else instance_fake_id_map[id_].id

        def correct_property_id(id_: int):
            return id_ if id_ not in property_fake_id_map else property_fake_id_map[id_].id

        def correct_tag_id(id_: int):
            return id_ if id_ not in tag_fake_id_map else tag_fake_id_map[id_].id

        instances_to_add = [i for i in data.instances if i.id < 0]
        if instances_to_add:
            new_instances = await self.project.db.add_instances(instances_to_add)
            if len(instances_to_add) != len(new_instances):
                raise Exception('instances_to_add and new_instances should have equal length. Unexpected behavior')
            for instance, new_instance in zip(instances_to_add, new_instances):
                instance_fake_id_map[instance.id] = new_instance

        properties_to_add = [p for p in data.properties if p.id < 0]
        if properties_to_add:
            new_properties = await self.project.db.add_properties(properties_to_add)
            if len(properties_to_add) != len(new_properties):
                raise Exception('properties_to_add and new_properties should have equal length. Unexpected behavior')
            for prop, new_prop in zip(properties_to_add, new_properties):
                property_fake_id_map[prop.id] = new_prop

        for t in data.tags:
            t.property_id = correct_property_id(t.property_id)
        tags_to_add = [tag for tag in data.tags if tag.id < 0]
        if tags_to_add:
            new_tags = await self.project.db.add_tags(tags_to_add)
            if len(tags_to_add) != len(new_tags):
                raise Exception("tags_to_add and new_tags should have equal length. Unexpected behavior")

            for tag, new_tag in zip(tags_to_add, new_tags):
                tag_fake_id_map[tag.id] = new_tag

        values = data.values
        for v in values:
            print(f"start property {v.property_id}")
            for chunk in chunk_list(list(zip(v.instance_ids, v.values)), 10000):
                ids, chunk_values = zip(*chunk)
                # print(ids, chunk_values)
                ids = [correct_instance_id(i) for i in ids]
                property_id = correct_property_id(v.property_id)
                # print(chunk_values[0])
                if isinstance(chunk_values[0], list):
                    # print('is tag')
                    chunk_values = [[correct_tag_id(tid) for tid in vals] for vals in chunk_values]
                await self.project.db.set_property_values_array(property_id, ids, chunk_values)
                # print(f"imported {len(chunk)} values")
        print("import finished")
