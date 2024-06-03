from __future__ import annotations

import datetime
import os
import shutil
from typing import List, TYPE_CHECKING

import pandas as pd
if TYPE_CHECKING:
    from panoptic.core.project.project import Project
from panoptic.models import PropertyType, Instance, Property


def _copy_images(images: List[Instance], destination_folder: str) -> None:
    os.makedirs(destination_folder, exist_ok=True)
    for image in images:
        # url = image.url.replace("/images/", "", 1)
        url = image.url
        try:
            shutil.copy(url, destination_folder)
        except BaseException:
            print(f'File {url} not found !')


def get_name(p: Property):
    if p.id == -1:
        return p.name
    return f'{p.name}[{p.type}]'


class Exporter:
    def __init__(self, project: Project):
        self.project = project

    async def export_data(self, path, name: str = None, instance_ids: [int] = None, properties=None,
                          copy_images: bool = False) -> str:
        if not name:
            name = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base_export_folder = os.path.join(path, 'exports')
        # Create the export folder if it doesn't exist
        os.makedirs(base_export_folder, exist_ok=True)

        export_folder = os.path.join(base_export_folder, name)
        if os.path.exists(export_folder):
            shutil.rmtree(export_folder)
        os.makedirs(export_folder)

        instances = await self.project.db.get_instances_with_properties(instance_ids)
        # Create a CSV file with the data
        if properties:
            data_file_path = os.path.join(export_folder, 'data.csv')
            df = await self._build_export_data(instances, properties)
            df.to_csv(data_file_path, index=False, sep=";")

        if copy_images:
            # Create a folder for images and copy them
            image_folder_path = os.path.join(export_folder, 'images')
            _copy_images(instances, image_folder_path)

        return export_folder

    async def _build_export_data(self, images: [Instance], properties_list: list[int]):
        """
        Allow to export selected images and properties into a csv file
        """
        properties = await self.project.db.get_properties(computed=True)
        tags = await self.project.db.get_tags()
        tag_index = {t.id: t for t in tags}

        folders = await self.project.db.get_folders()
        folder_index = {f.id: f for f in folders}

        # filter properties id that we want to keep
        id_to_prop = {p.id: p for p in properties}
        columns = [get_name(id_to_prop[p]) for p in properties_list]
        rows = []
        for image in images:
            row = []
            for prop_id in properties_list:
                prop = id_to_prop[prop_id]
                if prop.id in image.properties:
                    value = image.properties[prop.id].value
                    # if it's a tag let's fetch tag value from tag id
                    if prop.type == PropertyType.tag or prop.type == PropertyType.multi_tags:
                        # print('is tag !!')
                        if type(value) != list:
                            row.append(None)
                            continue
                        row.append(",".join([tag_index[t].value for t in value]))
                    elif prop.type == PropertyType.folder:
                        row.append(folder_index[value].name)
                    else:
                        row.append(value)
                else:
                    row.append(None)
            rows.append(row)
        df = pd.DataFrame.from_records(rows, columns=columns)
        return df
