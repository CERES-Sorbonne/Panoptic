import datetime
import os
import shutil
from typing import List

import pandas as pd


from panoptic.models import PropertyType, Instance


def _copy_images(images: List[Instance], destination_folder: str) -> None:
    os.makedirs(destination_folder, exist_ok=True)
    for image in images:
        url = image.url.replace("/images/", "", 1)
        try:
            shutil.copy(url, destination_folder)
        except BaseException:
            print(f'File {url} not found !')


async def _build_export_data(images: [Instance], properties_list=None):
    """
    Allow to export selected images and properties into a csv file
    """
    from panoptic.core import get_properties, get_tags
    properties = await get_properties()
    tags = await get_tags()

    # filter properties id that we want to keep
    properties_list = list(properties.keys()) if not properties_list else properties_list
    properties = [properties[pid] for pid in properties_list]
    columns = ["key", "sha1[string]"] + [f"{p.name}[{p.type.value}]" for p in properties]
    rows = []
    for image in images:
        row = [image.name, image.sha1]
        for prop in properties:
            if prop.id in image.properties:
                value = image.properties[prop.id].value
                # if it's a tag let's fetch tag value from tag id
                if prop.type == PropertyType.tag or prop.type == PropertyType.multi_tags:
                    if type(value) != list:
                        row.append(None)
                        continue
                    row.append(",".join([tags[prop.id][t].value for t in value]))
                else:
                    row.append(value)
            else:
                row.append(None)
        rows.append(row)
    df = pd.DataFrame.from_records(rows, columns=columns)
    return df


async def export_data(path, name: str = None, image_ids: [int] = None, properties=None, copy_images: bool = False) -> str:
    from panoptic.core import get_full_images
    if not name:
        name = str(datetime.datetime.now())
    base_export_folder = os.path.join(path, 'exports')
    # Create the export folder if it doesn't exist
    os.makedirs(base_export_folder, exist_ok=True)

    export_folder = os.path.join(base_export_folder, name)
    if os.path.exists(export_folder):
        shutil.rmtree(export_folder)
    os.makedirs(export_folder)

    images = await get_full_images(image_ids)
    # Create a CSV file with the data
    if properties:
        data_file_path = os.path.join(export_folder, 'data.csv')
        df = await _build_export_data(images, properties)
        df.to_csv(data_file_path, index=False)

    if copy_images:
        # Create a folder for images and copy them
        image_folder_path = os.path.join(export_folder, 'images')
        _copy_images(images, image_folder_path)

    return export_folder
