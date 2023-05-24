import atexit
import json
from concurrent.futures import ProcessPoolExecutor
from typing import List

from fastapi import HTTPException

from panoptic import compute
import panoptic.core.db
from panoptic.models import PropertyType, JSON, Image, Tag, Images, PropertyValue, Property, Tags, Properties, \
    UpdateTagPayload, UpdatePropertyPayload, Folder, ImageVector
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


async def get_images() -> Images:
    """
    Get all images from database
    """
    rows = await db.get_images()
    result = {}
    for row in rows:
        sha1, paths, height, width, url, extension, name, property_id, value, ahash = row
        if sha1 not in result:
            result[sha1] = Image(sha1=sha1, paths=json.loads(paths), width=width, height=height, url=url, name=name,
                                 extension=extension, ahash=ahash)
        if property_id:
            result[sha1].properties[property_id] = PropertyValue(
                **{'property_id': property_id, 'value': db.decode_if_json(value)})
    return result


async def make_clusters(sensibility: float, image_list: [str]) -> list[list[str]]:
    """
    Compute clusters and return a list of list of sha1
    """
    # TODO: add parameters to compute clusters only on some images
    images = await db.get_images_with_vectors(image_list)
    return compute.make_clusters(images, method="kmeans", nb_clusters=sensibility)


async def get_similar_images(sha1: str):
    images = await db.get_images_with_vectors([sha1])
    image = images[0]
    return compute.get_similar_images(image.vector)


async def add_property_to_image(property_id: int, sha1: str, value: JSON) -> str:
    # first check that the property and the image exist:
    if await db.get_property_by_id(property_id) and await db.get_image_by_sha1(sha1):
        # check if a value already exists
        if await db.get_image_property(sha1, property_id):
            await db.update_image_property(sha1, property_id, value)
        else:
            await db.add_image_property(sha1, property_id, value)
        return value
    else:
        raise HTTPException(status_code=400, detail="Trying to set a value on a non existent property or sha1")


async def delete_image_property(property_id: int, sha1: str):
    await db.delete_image_property(property_id, sha1)


async def add_image_to_db(file_path, name, extension, width, height, sha1_hash, url) -> Image:
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


async def add_folder(folder):
    found = await importer.import_folder(save_callback, folder)
    print(f'found {found} images')
    return folder


async def save_callback(image, folder_id: Folder, name, extension, width, height, sha1_hash, url, file_path):
    await add_image_to_db(folder_id, name, extension, width, height, sha1_hash, url)

    importer.compute_image(get_compute_callback(sha1_hash), image_path=file_path)


def get_compute_callback(sha1):
    async def callback(ahash, vector, is_last=False):
        await db.update_image_hashs(sha1, str(ahash), vector)
    return callback


@importer.set_final_callback
async def compute_finished_callback():
    images: list[ImageVector] = await db.get_images_with_vectors()
    compute.create_similarity_tree(images)


async def create_tag(property_id, value, parent_id, color:str) -> Tag:
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
    image_properties = await db.get_image_properties_with_tag(tag_id)
    # and delete the tag ref from them
    for image_property in image_properties:
        if tag_id in image_property.value:
            image_property.value.remove(tag_id)
        await db.update_image_property(image_property.sha1, image_property.property_id, image_property.value)
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
