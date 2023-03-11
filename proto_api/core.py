import hashlib
import json
import os
from PIL import Image as pImage
from fastapi import HTTPException

from models import PropertyType, JSON, Image, Tag, Images, PropertyValue, Property, Tags

import db_utils as db
from payloads import UpdateTagPayload


async def create_property(name: str, property_type: PropertyType) -> Property:
    return await db.add_property(name, property_type.value)


async def get_images() -> Images:
    """
    Get all images from database
    """
    rows = await db.get_images()
    result = {}
    for row in rows:
        sha1, paths, height, width, url, extension, name, property_id, property_name, property_type, value = row
        if sha1 not in result:
            result[sha1] = Image(sha1=sha1, paths=json.loads(paths), width=width, height=height, url=url, name=name, extension=extension)
        if property_id:
            result[sha1].properties[property_id] = PropertyValue(**{'id': property_id, 'name': property_name, 'type': property_type,
                                                                    'value': db.decode_if_json(value)})
    return result


async def add_property_to_image(property_id: int, sha1: str, value: JSON) -> str:
    # first check that the property and the image exist:
    if await db.get_property_by_id(property_id) and await db.get_image_by_sha1(sha1):
        await db.add_image_property(sha1, property_id, value)
        return value
    else:
        raise HTTPException(status_code=400, detail="Trying to set a value on a non existent property or sha1")


async def delete_image_property(property_id: int, sha1: str):
    await db.delete_image_property(property_id, sha1)


async def add_image(file_path) -> Image:
    image = pImage.open(file_path)
    name = file_path.split(os.sep)[-1]
    extension = name.split('.')[-1]
    width, height = image.size
    sha1_hash = hashlib.sha1(image.tobytes()).hexdigest()
    # TODO: gérer l'url statique quand on sera en mode serveur
    # url = os.path.join('/static/' + file_path.split(os.getenv('PANOPTIC_ROOT'))[1].replace('\\', '/'))
    url = f"/images/{file_path}"

    # Vérification si sha1_hash existe déjà dans la table images
    image = await db.get_image_by_sha1(sha1_hash)
    # Si sha1_hash existe déjà, on ajoute file_path à la liste de paths
    if image:
        if file_path not in image.paths:
            image.paths.append(file_path)
            # Mise à jour de la liste de paths
            await db.update_image_paths(sha1_hash, json.dumps(image.paths))

    # Si sha1_hash n'existe pas, on l'ajoute avec la liste de paths contenant file_path
    else:
        await db.add_image(sha1_hash, height, width, name, extension, json.dumps([file_path]), url)
    return await db.get_image_by_sha1(sha1_hash)


async def create_tag(property_id, value, parent_id) -> Tag:
    existing_tag = await db.get_tag(property_id, value)
    if existing_tag is not None:
        if db.tag_in_ancestors(existing_tag.id, parent_id):
            raise HTTPException(status_code=400, detail="Adding a tag that is an ancestor of himself")
        existing_tag.parents = list({*existing_tag.parents, parent_id})
        await db.update_tag(existing_tag)
        tag_id = existing_tag.id
    else:
        parents = [parent_id]
        tag_id = await db.add_tag(property_id, value, json.dumps(parents))
    return await db.get_tag_by_id(tag_id)


async def update_tag(payload: UpdateTagPayload) -> Tag:
    existing_tag = await db.get_tag_by_id(payload.id)
    if not existing_tag:
        raise HTTPException(status_code=400, detail="Trying to modify non existent tag")
    if db.tag_in_ancestors(existing_tag.id, payload.parent_id):
        raise HTTPException(status_code=400, detail="Adding a tag that is an ancestor of himself")
    # change only fields of the tags that are set in the payload
    new_tag = existing_tag.copy(update=payload.dict(exclude_unset=True))
    return await db.update_tag(new_tag)


async def get_tags(prop: str = None) ->Tags:
    res = {}
    tag_list = await db.get_tags(prop)
    for tag in tag_list:
        if tag.property_id not in res:
            res[tag.property_id] = {}
        res[tag.property_id][tag.id] = tag
    return res
