import concurrent.futures
import hashlib
import json
import os
from typing import List

from PIL import Image as pImage
from fastapi import HTTPException

from models import PropertyType, JSON, Image, Tag, Images, PropertyValue, Property, Tags, Properties

import db_utils as db
from payloads import UpdateTagPayload, UpdatePropertyPayload


def create_property(name: str, property_type: PropertyType) -> Property:
    return db.add_property(name, property_type.value)


def update_property(payload: UpdatePropertyPayload) -> Property:
    existing_property = db.get_property_by_id(payload.id)
    if not existing_property:
        raise HTTPException(status_code=400, detail="Trying to modify non existent property")
    new_property = existing_property.copy(update=payload.dict(exclude_unset=True))
    db.update_property(new_property)
    return new_property


def get_properties() -> Properties:
    properties = db.get_properties()
    return {prop.id: prop for prop in properties}


def delete_property(property_id: str):
    db.delete_property(property_id)


def get_images() -> Images:
    """
    Get all images from database
    """
    rows = db.get_images()
    result = {}
    for row in rows:
        sha1, paths, height, width, url, extension, name, property_id, value = row
        if sha1 not in result:
            result[sha1] = Image(sha1=sha1, paths=json.loads(paths), width=width, height=height, url=url, name=name,
                                 extension=extension)
        if property_id:
            result[sha1].properties[property_id] = PropertyValue(
                **{'property_id': property_id, 'value': db.decode_if_json(value)})
    return result


def add_property_to_image(property_id: int, sha1: str, value: JSON) -> str:
    # first check that the property and the image exist:
    if db.get_property_by_id(property_id) and db.get_image_by_sha1(sha1):
        # check if a value already exists
        if db.get_image_property(sha1, property_id):
            db.update_image_property(sha1, property_id, value)
        else:
            db.add_image_property(sha1, property_id, value)
        return value
    else:
        raise HTTPException(status_code=400, detail="Trying to set a value on a non existent property or sha1")


def delete_image_property(property_id: int, sha1: str):
    db.delete_image_property(property_id, sha1)


def _proprocess_image(file_path):
    image = pImage.open(file_path)
    name = file_path.split(os.sep)[-1]
    extension = name.split('.')[-1]
    width, height = image.size
    sha1_hash = hashlib.sha1(image.tobytes()).hexdigest()
    # TODO: gérer l'url statique quand on sera en mode serveur
    # url = os.path.join('/static/' + file_path.split(os.getenv('PANOPTIC_ROOT'))[1].replace('\\', '/'))
    url = f"/images/{file_path}"
    return name, extension, width, height, sha1_hash, url


def add_image(file_path) -> Image:
    name, extension, width, height, sha1_hash, url = _proprocess_image(file_path)
    # Vérification si sha1_hash existe déjà dans la table images
    return add_image_to_db(file_path, name, extension, width, height, sha1_hash, url)


def add_image_to_db(file_path, name, extension, width, height, sha1_hash, url) -> Image:
    image = db.get_image_by_sha1(sha1_hash)
    # Si sha1_hash existe déjà, on ajoute file_path à la liste de paths
    if image:
        if file_path not in image.paths:
            image.paths.append(file_path)
            # Mise à jour de la liste de paths
            db.update_image_paths(sha1_hash, json.dumps(image.paths))

    # Si sha1_hash n'existe pas, on l'ajoute avec la liste de paths contenant file_path
    else:
        db.add_image(sha1_hash, height, width, name, extension, json.dumps([file_path]), url)
    return db.get_image_by_sha1(sha1_hash)


def add_folder(folder):
    folders = db.get_parameters().folders
    db.update_folders(list({folder, *folders}))
    all_files = [os.path.join(path, name) for path, subdirs, files in os.walk(folder) for name in files]
    all_images = [i for i in all_files if
                  i.lower().endswith('.png') or i.lower().endswith('.jpg') or i.lower().endswith('.jpeg')]
    with concurrent.futures.ProcessPoolExecutor() as executor:
        transformed = [executor.submit(_proprocess_image, i) for i in all_images]
    for future, path in zip(concurrent.futures.as_completed(transformed), all_images):
        add_image_to_db(path, *future.result())
    return len(all_images)


def create_tag(property_id, value, parent_id) -> Tag:
    existing_tag = db.get_tag(property_id, value)
    if existing_tag is not None:
        if db.tag_in_ancestors(existing_tag.id, parent_id):
            raise HTTPException(status_code=400, detail="Adding a tag that is an ancestor of himself")
        existing_tag.parents = list({*existing_tag.parents, parent_id})
        db.update_tag(existing_tag)
        tag_id = existing_tag.id
    else:
        parents = [parent_id]
        tag_id = db.add_tag(property_id, value, json.dumps(parents))
    return db.get_tag_by_id(tag_id)


def update_tag(payload: UpdateTagPayload) -> Tag:
    existing_tag = db.get_tag_by_id(payload.id)
    if not existing_tag:
        raise HTTPException(status_code=400, detail="Trying to modify non existent tag")
    if db.tag_in_ancestors(existing_tag.id, payload.parent_id):
        raise HTTPException(status_code=400, detail="Adding a tag that is an ancestor of himself")
    # change only fields of the tags that are set in the payload
    new_tag = existing_tag.copy(update=payload.dict(exclude_unset=True))
    db.update_tag(new_tag)
    return new_tag


def delete_tag(tag_id: int) -> List[int]:
    # first delete the tag
    modified_tags = [db.delete_tag_by_id(tag_id)]
    # when deleting a tag, get all children of this tag
    children = db.get_tags_by_parent_id(tag_id)
    # and remove parent ref of tag in children
    [modified_tags.extend(delete_tag_parent(c, tag_id)) for c in children]
    # then get all images properties tagged with it
    image_properties = db.get_image_properties_with_tag(tag_id)
    # and delete the tag ref from them
    for image_property in image_properties:
        image_property.value.remove(tag_id)
        db.update_image_property(image_property.sha1, image_property.property_id, image_property.value)
    return modified_tags


def delete_tag_parent(tag_id: int, parent_id: int) -> List[int]:
    tag = db.get_tag_by_id(tag_id)
    tag.parents.remove(parent_id)
    if not tag.parents:
        return delete_tag(tag.id)
    else:
        db.update_tag(tag)
        return []


def get_tags(prop: str = None) -> Tags:
    res = {}
    tag_list = db.get_tags(prop)
    for tag in tag_list:
        if tag.property_id not in res:
            res[tag.property_id] = {}
        res[tag.property_id][tag.id] = tag
    return res
