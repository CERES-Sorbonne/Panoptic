import asyncio
import csv
from dataclasses import dataclass
from enum import Enum

import pandas as pd
from pydantic import BaseModel
from typing import TYPE_CHECKING

from panoptic.core.project.project import Project
from panoptic.models import PropertyType, PropertyMode


# if TYPE_CHECKING:
#     from panoptic.core.project.project import Project
# from panoptic.models import PropertyMode, Property
#
#
# class ColumnImportOption(BaseModel):
#     index: int
#     mode: PropertyMode
#

class ColumnOption(BaseModel):
    ignore = False
    property_mode: PropertyMode | None


Option = dict[int, ColumnOption]


# class ImportMode(Enum):
#     update = 'update'
#     create = 'create'

#
# class ImportRequest(BaseModel):
#     file: str
#     columns: list[ColumnImportOption]
#

def parse_header(index: int, name: str):
    name, remain = name.split('[')
    type_ = PropertyType(remain.split(']')[0])
    return index, name, type_


class Importer:
    def __init__(self, project: None):
        self.project = project

    async def import_file(self, file: str, options: Option):
        project = Project('/Users/david/panoptic-projects/last2', [])
        await project.start()
        with open(file, 'r') as file:
            # Create a CSV reader object
            reader = csv.reader(file, delimiter=';')

            first_row = next(reader)

            file_key = first_row[0]
            file_props = [parse_header(i + 1, col_name) for i, col_name in enumerate(first_row[1:]) if col_name]
            file_props = [p for p in file_props if not (p[0] in options and options[p[0]].ignore)]

            col_to_id: dict[int, int] = {}
            # print(file_props)
            db_props = await project.db.get_properties()
            for prop in db_props:
                for col_i, name, type_ in file_props:
                    if name == prop.name and type_ == prop.type:
                        col_to_id[col_i] = prop.id

            for col_i, name, type_ in file_props:
                if col_i not in col_to_id:
                    mode = options[col_i].property_mode if col_i in options else PropertyMode.id
                    mode = PropertyMode.id if not mode else mode
                    print('create property: ', name, type_, mode)
                    new_prop = await project.db.add_property(name, type_, mode.value)
                    col_to_id[col_i] = new_prop.id
            # print(col_to_id)

            rows = list(reader)

            row_to_id: dict[int, int] = {}
            if file_key == '#':
                [row_to_id.update({i: int(row[0])}) for i, row in enumerate(rows)]
            if file_key == '/':
                instances = await project.db.empty_or_clone([r[0] for r in rows])
                [row_to_id.update({i: instance.id}) for i, instance in enumerate(instances)]

            property_ids = col_to_id.values()
            property_values: dict[int, list] = {i: [] for i in property_ids}
            for col_i in col_to_id.keys():
                for row_i, row in enumerate(rows):
                    property_values[col_to_id[col_i]].append((row_to_id[row_i], row[col_i]))

            for prop_id, pairs in property_values.items():
                ids, values = zip(*pairs)
                await project.db.set_property_values_array(prop_id, ids, values)

        await project.close()


async def launch():
    importer = Importer(None)
    await importer.import_file('/Users/david/Documents/test-import.csv', {1: ColumnOption(property_mode=PropertyMode.sha1)})


asyncio.run(launch())
