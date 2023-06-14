import atexit
import json
import logging
import random
from concurrent.futures import ProcessPoolExecutor
import time
from typing import List, Any

import pandas
from fastapi import HTTPException
from tqdm import tqdm

from panoptic.core import db
from panoptic import compute
from panoptic.models import PropertyType, JSON, Tag, Property, Tags, Properties, \
    UpdateTagPayload, UpdatePropertyPayload, Image, PropertyValue
from .image_importer import ImageImporter
from .image_importer import ImageImporter

executor = ProcessPoolExecutor(max_workers=4)
atexit.register(executor.shutdown)
importer = ImageImporter(executor)


async def create_property(name: str, property_type: PropertyType, mode='id') -> Property:
    return await db.add_property(name, property_type.value, mode)


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


async def set_property_values(property_id: int, value: Any, image_ids: List[int] = None, sha1s: List[int] = None):
    if image_ids and sha1s:
        raise TypeError('Only image_ids or sha1s should be given as keys. Never both')

    prop = await db.get_property_by_id(property_id)
    if prop.mode == 'id' and not image_ids:
        raise TypeError(f'Property {property_id}: {prop.name} needs image ids as key [mode: {prop.mode}]')
    if prop.mode == 'sha1' and not sha1s:
        raise TypeError(f'Property {property_id}: {prop.name} needs sha1s as key [mode: {prop.mode}]')

    if prop.type == PropertyType.tag or prop.type == PropertyType.multi_tags:
        if value and not isinstance(value, list):
            value = [int(value)]

    return await db.set_property_values(property_id, value, image_ids, sha1s)


async def get_full_images(image_ids: List[int] = None) -> List[Image]:
    images = await db.get_images(image_ids)
    sha1s = list({img.sha1 for img in images})
    property_values = await db.get_property_values(image_ids=image_ids)
    ahashs = await db.get_sha1_ahashs(sha1s=sha1s)
    image_index = {img.id: img for img in images}

    def assign_value(prop):
        image_index[prop.image_id].properties[prop.property_id] = prop

    [assign_value(prop) for prop in property_values if prop.image_id >= 0]

    sha1_properties = {}

    def register_sha1_value(prop: PropertyValue):
        if prop.sha1 not in sha1_properties:
            sha1_properties[prop.sha1] = []
        sha1_properties[prop.sha1].append(prop)

    [register_sha1_value(prop) for prop in property_values if prop.image_id < 0]

    def assign_sha1_value(image_id, prop: PropertyValue):
        image_index[image_id].properties[prop.property_id] = prop

    [assign_sha1_value(img.id, prop) for img in images if img.sha1 in sha1_properties for prop in
     sha1_properties[img.sha1]]

    [setattr(img, 'ahash', ahashs[img.sha1]) for img in images if img.sha1 in ahashs]
    return images


async def make_clusters(sensibility: float, sha1s: [str]) -> list[list[str]]:
    """
    Compute clusters and return a list of lists of sha1
    """
    if not sha1s:
        return []
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
    filenames, ids = zip(*[(i.name, i.id) for i in await db.get_images()])
    matcher = dict(zip(filenames, ids))
    data = data[data.key.isin(filenames)]
    # data = data.drop_duplicates(subset='key', keep='first')
    # add property id to the dataframe
    data.loc[data.index, 'panoptic_id'] = data['key'].map(matcher)

    # first, create new images where ids are the same
    unique_ids = list(data.panoptic_id.unique())
    clones_created = 0
    # TODO: create clones all at once ? it's tricky with the ids to update
    for id in tqdm(unique_ids):
        sub_data = data[data.panoptic_id == id]
        image = await db.get_images([id])
        image = image[0]
        new_ids = await db.create_clones(image, sub_data.shape[0] - 1)
        clones_created += len(new_ids)
        data.loc[data.panoptic_id == id, "panoptic_id"] = [image.id, *new_ids]
    logging.getLogger('panoptic').info(f"created {clones_created} new images")
    properties_to_create = data.columns.tolist()

    # then for each property to create
    for prop in properties_to_create:
        if prop == "key" or prop == "panoptic_id":
            continue
        # create the property
        prop_name, prop_type = prop.split('[')
        prop_type = PropertyType(prop_type.split(']')[0])
        property = await create_property(prop_name, prop_type)
        # then get all possible values to insert
        prop_values = list(data[prop].unique())

        # if it's a tag property let's create the tags in the db
        if property.type == PropertyType.tag or property.type == PropertyType.multi_tags:
            tag_matcher = {}
            # TODO: can we optimize to create all tags at once ?
            for value in tqdm(prop_values):
                created_tags = []
                # if it's multi tag, assume tags are separated by a comma and create them separately
                for single_tag in value.split(','):
                    colors = ["7c1314", "c31d20", "f94144", "f3722c", "f8961e", "f9c74f", "90be6d", "43aa8b", "577590",
                              "9daebe"]
                    color = '#' + colors[random.randint(0, len(colors) - 1)]
                    tag = await create_tag(property.id, single_tag, 0, color)
                    created_tags.append(tag.id)
                tag_matcher[value] = created_tags
            # now change all values in the dataframe with the real value that we are going to insert
            data.loc[data.index, prop] = data[prop].map(tag_matcher)
        await db.set_multiple_property_values(property.id, list(data[prop]), list(data.panoptic_id))


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
