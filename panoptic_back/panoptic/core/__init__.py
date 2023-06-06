import atexit
import json
import random
from concurrent.futures import ProcessPoolExecutor
from typing import List

import pandas
from fastapi import HTTPException

import panoptic.core.db
import panoptic.core.db
from panoptic import compute
from panoptic.models import PropertyType, JSON, Tag, Property, Tags, Properties, \
    UpdateTagPayload, UpdatePropertyPayload, Image2
from .image_importer import ImageImporter
from .image_importer import ImageImporter

executor = ProcessPoolExecutor(max_workers=4)
atexit.register(executor.shutdown)
importer = ImageImporter(executor)


async def create_property(name: str, property_type: PropertyType) -> Property:
    return await db.add_property(name, property_type.value)


async def update_property(payload: UpdatePropertyPayload) -> Property:
    existing_property = await db.get_property_by_id(payload.id)
    if not existing_property:
        raise HTTPException(status_code=400, detail="Trying to modify non existent property")
    new_property = existing_property.copy(update=payload.dict(exclude_unset=True))
    await db.update_property(new_property)
    return new_property


async def get_properties() -> Properties:
    properties = await db.get_properties()
    return {prop.id: prop for prop in properties}


async def delete_property(property_id: str):
    await db.delete_property(property_id)


async def get_full_images(image_ids: List[int] = None) -> List[Image2]:
    images = await db.get_images(image_ids)
    sha1s = list({img.sha1 for img in images})
    property_values = await db.get_property_values(image_ids=image_ids)
    ahashs = await db.get_sha1_ahashs(sha1s=sha1s)
    image_index = {img.id: img for img in images}

    def assign_value(prop):
        image_index[prop.image_id].properties[prop.property_id] = prop
    [assign_value(prop) for prop in property_values]
    [setattr(img, 'ahash', ahashs[img.sha1]) for img in images if img.sha1 in ahashs]
    return images


async def make_clusters(sensibility: float, sha1s: [str]) -> list[list[str]]:
    """
    Compute clusters and return a list of lists of sha1
    """
    if not sha1s:
        return []
    # TODO: add parameters to compute clusters only on some images
    values = await db.get_sha1_computed_values(sha1s)
    return compute.make_clusters(values, method="kmeans", nb_clusters=sensibility)


async def get_similar_images(sha1s: list[str]):
    vectors = [i.vector for i in await db.get_sha1_computed_values(sha1s)]
    res = compute.get_similar_images(vectors)
    return [img for img in res if img['sha1'] not in sha1s]


async def add_property_to_images(property_id: int, sha1_list: list[str], value: JSON) -> str:
    # first check that the property and the image exist:
    images = await db.get_images(sha1s=sha1_list)
    if await db.get_property_by_id(property_id) and images:
        await db.set_property_values(image_ids=[img.id for img in images], property_id=property_id, value=value)
        # check if a value already exists
        # if await db.get_image_property(sha1, property_id):
        #     await db.update_image_property(sha1, property_id, value)
        # else:
        #     await db.add_image_property(sha1, property_id, value)
        return value
    else:
        raise HTTPException(status_code=400, detail="Trying to set a value on a non existent property or sha1")


async def read_properties_file(data: pandas.DataFrame):
    filenames, sha1s = zip(*[(i.name, i.sha1) for i in await db.get_images()])
    data = data[data.key.isin(filenames)]
    data = data.drop_duplicates(subset='key', keep='first')
    for f, s in zip(filenames, sha1s):
        data.loc[data.key == f, 'sha1'] = s

    properties_to_create = data.columns.tolist()

    for prop in properties_to_create:
        if prop == "key" or prop == "sha1":
            continue
        prop_name, prop_type = prop.split('[')
        prop_type = PropertyType(prop_type.split(']')[0])
        property = await create_property(prop_name, prop_type)
        prop_values = list(data[prop].unique())
        for value in prop_values:
            real_value = value
            if property.type == PropertyType.tag.value or property.type == PropertyType.multi_tags.value:
                colors = ["7c1314", "c31d20", "f94144", "f3722c", "f8961e", "f9c74f", "90be6d", "43aa8b", "577590",
                          "9daebe"]
                color = colors[random.randint(0, len(colors) - 1)]
                tag = await create_tag(property.id, value, 0, color)
                real_value = [tag.id]
            sub_data = data[data[prop] == value]
            await add_property_to_images(property.id, sub_data.sha1.tolist(), real_value)

async def add_folder(folder):
    found = await importer.import_folder(folder)
    print(f'found {found} images')
    return folder


new_images = []


def get_new_images():
    copy = [i for i in new_images]
    new_images.clear()
    return copy


async def create_tag(property_id, value, parent_id, color: str) -> Tag:
    existing_tag = await db.get_tag(property_id, value)
    if existing_tag is not None:
        if await db.tag_in_ancestors(existing_tag.id, parent_id):
            raise HTTPException(status_code=400, detail="Adding a tag that is an ancestor of himself")
        existing_tag.parents = list({*existing_tag.parents, parent_id})
        await db.update_tag(existing_tag)
        tag_id = existing_tag.id
    else:
        parents = [parent_id]
        tag_id = await db.add_tag(property_id, value, json.dumps(parents), color)
    return await db.get_tag_by_id(tag_id)


async def update_tag(payload: UpdateTagPayload) -> Tag:
    existing_tag = await db.get_tag_by_id(payload.id)
    if not existing_tag:
        raise HTTPException(status_code=400, detail="Trying to modify non existent tag")
    if await db.tag_in_ancestors(existing_tag.id, payload.parent_id):
        raise HTTPException(status_code=400, detail="Adding a tag that is an ancestor of himself")
    # change only fields of the tags that are set in the payload
    new_tag = existing_tag.copy(update=payload.dict(exclude_unset=True))
    await db.update_tag(new_tag)
    return new_tag


async def delete_tag(tag_id: int) -> List[int]:
    # first delete the tag
    modified_tags = [await db.delete_tag_by_id(tag_id)]
    # when deleting a tag, get all children of this tag
    children = await db.get_tags_by_parent_id(tag_id)
    # and remove parent ref of tag in children
    [modified_tags.extend(await delete_tag_parent(c.id, tag_id)) for c in children]
    # then get all images properties tagged with it
    property_values = await db.get_property_values_with_tag(tag_id)
    # and delete the tag ref from them
    for data in property_values:
        if tag_id in data.value:
            data.value.remove(tag_id)
            await db.set_property_values(data.property_id, data.value, [data.image_id])
    return modified_tags


async def delete_tag_parent(tag_id: int, parent_id: int) -> List[int]:
    print(tag_id, parent_id)
    tag = await db.get_tag_by_id(tag_id)
    tag.parents.remove(parent_id)
    if not tag.parents:
        return await delete_tag(tag.id)
    else:
        await db.update_tag(tag)
        return []


async def get_tags(prop: str = None) -> Tags:
    res = {}
    tag_list = await db.get_tags(prop)
    for tag in tag_list:
        if tag.property_id not in res:
            res[tag.property_id] = {}
        res[tag.property_id][tag.id] = tag
    return res
