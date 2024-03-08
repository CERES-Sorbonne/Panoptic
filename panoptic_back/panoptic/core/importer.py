from __future__ import annotations

import csv
from collections import defaultdict

import pandas as pd
from random import randint
from typing import TYPE_CHECKING

from fastapi import UploadFile

if TYPE_CHECKING:
    from panoptic.core.project.project import Project
from panoptic.models import PropertyType, PropertyMode, PropertyDescription, Tag, Property, ImportOptions, SetMode


def parse_list(value: str):
    if value is None or value == '':
        return None
    # value = value.replace('[', '')
    # value = value.replace(']', '')
    return value.split(',')


def parse_header(index: int, name: str):
    name, remain = name.split('[')
    type_ = PropertyType(remain.split(']')[0])
    return index, name, type_


class Importer:
    def __init__(self, project: Project):
        self.project = project
        self._df: pd.DataFrame | None = None

    async def upload_csv(self, file: UploadFile):
        file_data = pd.read_csv(file.file, delimiter=';', encoding='utf-8')
        self._df = file_data

        return True

    async def import_file(self, options: ImportOptions):
        # TODO: refactor all this to use pandas methods properly
        # Read first row to determine properties
        columns = list(self._df.columns)
        file_key = columns[0]
        file_props = [parse_header(i + 1, col_name) for i, col_name in enumerate(columns[1:]) if col_name]
        file_props = [p for p in file_props if not (p[0] in options and options[p[0]].ignore)]

        # map of col index to property id
        col_to_prop: dict[int, Property] = {}

        # map col to existing property if possible
        db_props = await self.project.db.get_properties()
        for prop in db_props:
            for col_i, name, type_ in file_props:
                if name == prop.name and type_ == prop.type:
                    col_to_prop[col_i] = prop

        # create missing properties and add to map
        for col_i, name, type_ in file_props:
            if col_i not in col_to_prop:
                # use options info to determine property mode
                mode = options[col_i].property_mode if col_i in options else PropertyMode.id
                # fallback to id mode if None
                mode = PropertyMode.id if not mode else mode
                print('create property: ', name, type_, mode)
                new_prop = await self.project.db.add_property(name, type_, mode.value)
                col_to_prop[col_i] = new_prop

        # read full csv
        row_to_id: dict[int, int] = {}
        # map every row to and instance id
        if file_key == 'id':
            id_list = list(self._df.id)
            [row_to_id.update({i: id_}) for i, id_ in enumerate(id_list)]
        # if file path give map to an existing and empty instance or a new clone
        if file_key == '/':
            path_list = list(self._df.path)
            instances = await self.project.db.empty_or_clone(path_list)
            [row_to_id.update({i: instance.id}) for i, instance in enumerate(instances)]

        # for each property create arrays of (instance_id, value) pairs
        property_ids = [p.id for p in col_to_prop.values()]
        property_values: dict[int, list] = {i: [] for i in property_ids}

        for col_i in col_to_prop.keys():
            for r in self._df.iterrows():
                index, row = r
                property_values[col_to_prop[col_i].id].append((row_to_id[index], row[col_i]))

        # for each property set the property values
        for prop_id, pairs in property_values.items():
            ids, values = zip(*pairs)
            properties = list(col_to_prop.values())
            prop = properties[[p.id for p in properties].index(prop_id)]
            # if is tag or multi_tags property check tags first
            if prop.type == PropertyType.multi_tags or prop.type == PropertyType.tag:
                # map tag name to db_tag
                tags = await self.project.db.get_tags(prop_id)
                name_to_tag: dict[str, Tag] = {t.value: t for t in tags}
                values = [parse_list(v) for v in values]
                if prop.type == PropertyType.tag:
                    values = [[v[0]] if v else v for v in values]
                import_tags = set([t for v in values if v for t in v])

                # create missing tags
                to_create = [t for t in import_tags if t not in name_to_tag]
                for tag_name in to_create:
                    tag = await self.project.db.add_tag(prop_id, tag_name, None, randint(0, 11))
                    name_to_tag[tag.value] = tag
                # replace tag names by tag ids
                values = [[name_to_tag[t].id for t in v] if v else None for v in values]
                for id_, value in zip(ids, values):
                    await self.project.db.set_tag_property_value(prop_id, [id_], value, SetMode.add)
            else:
                await self.project.db.set_property_values_array(prop_id, ids, values)

    async def analyse_file(self):
        # TODO: refactor all this to use pandas methods properly
        if self._df is None:
            raise Exception('No csv file was uploaded')

        # Read first row to determine properties
        columns = list(self._df.columns)
        file_key = columns[0]
        file_props = [parse_header(i + 1, col_name) for i, col_name in enumerate(columns[1:]) if col_name]
        properties = await self.project.db.get_properties(no_computed=True)
        col_to_prop: dict[int, PropertyDescription] = {}

        for i, name, type_ in file_props:
            col_to_prop[i] = PropertyDescription(name=name, type=type_, mode=PropertyMode.sha1, col=i)

        for prop in properties:
            for desc in col_to_prop.values():
                if desc.name == prop.name and desc.type == prop.type:
                    desc.id = prop.id
                    desc.mode = prop.mode

        import_props = list(col_to_prop.values())

        row_to_sha1: dict[int, str] = {}
        instances = await self.project.db.get_instances()
        key_desc = PropertyDescription(col=0, name='key', type=None, mode=PropertyMode.id)
        if file_key == 'id':
            key_desc.type = PropertyType.id
            key_desc.id = -1
            id_to_sha1 = {i.id: i.sha1 for i in instances}
            id_list = list(self._df.id)
            [row_to_sha1.update({i: id_to_sha1[id_]}) for i, id_ in enumerate(id_list)]
        if file_key == '/':
            key_desc.id = -7
            key_desc.type = PropertyType.path
            path_list = list(self._df.path)
            path_to_sha1 = {p: None for p in [path for path in path_list]}
            [path_to_sha1.update({i.url: i.sha1}) for i in instances if i.url in path_to_sha1]
            empties = [k for k in path_to_sha1.keys() if path_to_sha1[k] is None]
            if empties:
                raise Exception(f'{len(empties)} path(s) not found ' + ','.join([e for e in empties]))
            [row_to_sha1.update({i: path_to_sha1[path]}) for i, path in enumerate(path_list)]

        for prop in [p for p in import_props if p.id is None]:
            sha1_values = defaultdict(list)
            for r in self._df.iterrows():
                index, row = r
                values = sha1_values[row_to_sha1[index]]
                values.append(row.iloc[prop.col])
                if values[0] != row.iloc[prop.col]:
                    prop.mode = PropertyMode.id
                    break

        return [key_desc, *import_props]

