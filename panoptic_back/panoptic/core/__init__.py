# import atexit
# import json
# import logging
# import os
# import random
# import sys
# from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
# from typing import List, Any
#
#
# import pandas
# from fastapi import HTTPException
# from tqdm import tqdm
#
# from panoptic import compute
# from .db import db
# from panoptic.models import PropertyType, JSON, Tag, Property, Tags, Properties, \
#     UpdateTagPayload, UpdatePropertyPayload, Instance, PropertyValue, Clusters
# from .image_importer import ImageImporter
#
# nb_workers = 4
# executor = ThreadPoolExecutor(max_workers=nb_workers) if any(
#     [os.getenv('IS_DOCKER', False), sys.platform.startswith('linux')]) else ProcessPoolExecutor(
#     max_workers=nb_workers)
# atexit.register(executor.shutdown)
# importer = ImageImporter(executor)
#
#
# async def clear_import():
#     await importer.clear()
#
#
# async def create_property(name: str, property_type: PropertyType, mode='id') -> Property:
#     return await db.add_property(name, property_type.value, mode)
#
#
# async def update_property(payload: UpdatePropertyPayload) -> Property:
#     existing_property = await db.get_property_by_id(payload.id)
#     if not existing_property:
#         raise HTTPException(status_code=400, detail="Trying to modify non existent property")
#     new_property = existing_property.copy(update=payload.dict(exclude_unset=True))
#     await db.update_property(new_property)
#     return new_property
#
#
# async def get_properties() -> Properties:
#     properties = await db.get_properties()
#     return {prop.id: prop for prop in properties}
#
#
# async def delete_property(property_id: str):
#     await db.delete_property(property_id)
#
#
# async def set_property_values(property_id: int, value: Any, image_ids: List[int] = None, sha1s: List[int] = None):
#     if image_ids and sha1s:
#         raise TypeError('Only image_ids or sha1s should be given as keys. Never both')
#
#     prop = await db.get_property_by_id(property_id)
#     if prop.mode == 'id' and not image_ids:
#         raise TypeError(f'Property {property_id}: {prop.name} needs image ids as key [mode: {prop.mode}]')
#     if prop.mode == 'sha1' and not sha1s:
#         raise TypeError(f'Property {property_id}: {prop.name} needs sha1s as key [mode: {prop.mode}]')
#
#     if prop.id == PropertyType.tag or prop.id == PropertyType.multi_tags:
#         if value and not isinstance(value, list):
#             value = [int(value)]
#
#     if prop.id == PropertyType.checkbox:
#         value = True if value == 'true' or value is True else False
#
#     return await db.set_property_values(property_id, value, image_ids, sha1s)
#
#
# async def add_property_values(property_id: int, value: Any, image_ids: List[int] = None, sha1s: List[int] = None):
#     if image_ids and sha1s:
#         raise TypeError('Only image_ids or sha1s should be given as keys. Never both')
#
#     prop = await db.get_property_by_id(property_id)
#     if prop.mode == 'id' and not image_ids:
#         raise TypeError(f'Property {property_id}: {prop.name} needs image ids as key [mode: {prop.mode}]')
#     if prop.mode == 'sha1' and not sha1s:
#         raise TypeError(f'Property {property_id}: {prop.name} needs sha1s as key [mode: {prop.mode}]')
#
#     if prop.id != PropertyType.multi_tags:
#         raise TypeError('add_property_values is only supported for multi_tag properties')
#
#     if value and not isinstance(value, list):
#         value = [int(value)]
#
#     current_values = await db.get_property_values(property_ids=[property_id], image_ids=image_ids, sha1s=sha1s)
#     if image_ids:
#         value_index = {v.image_id: v.value for v in current_values}
#         [value_index.update({id_: []}) for id_ in image_ids if id_ not in value_index]
#         [value_index[id_].extend(value) for id_ in image_ids]
#         values = [list(set(value_index[id_])) for id_ in image_ids]
#         await db.set_multiple_property_values(property_id, values, image_ids)
#     else:
#         value_index = {v.sha1: v.value for v in current_values}
#         [value_index.update({sha1: []}) for sha1 in sha1s if sha1 not in value_index]
#         [value_index[sha1].extend(value) for sha1 in sha1s]
#         values = [list(set(value_index[sha1])) for sha1 in sha1s]
#         await db.set_multiple_property_values(property_id, values, sha1s)
#
#     updated_ids = image_ids
#     if not image_ids:
#         images = await db.get_images(sha1s=sha1s)
#         updated_ids = [img.id for img in images]
#     return updated_ids, value
#
#
# async def get_full_images(image_ids: List[int] = None) -> List[Instance]:
#     images = await db.get_images(image_ids)
#     sha1s = list({img.sha1 for img in images})
#     # get ids bound property values
#     property_values = await db.get_property_values(image_ids=image_ids)
#     # get sha1 bound property values when image_ids is set and therefore property_values only return id bound properties
#     if image_ids:
#         sha1s_values = await db.get_property_values(sha1s=sha1s)
#         property_values += sha1s_values
#     ahashs = await db.get_sha1_ahashs(sha1s=sha1s)
#     image_index = {img.id: img for img in images}
#
#     def assign_value(prop_value):
#         image_index[prop_value.image_id].properties[prop_value.property_id] = prop_value
#
#     # fill the index with ids bound property values
#     [assign_value(prop_value) for prop_value in property_values if prop_value.image_id >= 0]
#
#     sha1_properties = {}
#
#     def register_sha1_value(prop_value: PropertyValue):
#         if prop_value.sha1 not in sha1_properties:
#             sha1_properties[prop_value.sha1] = []
#         sha1_properties[prop_value.sha1].append(prop_value)
#
#     # populate the index of sha1 properties with prop_values that are bound to sha1s
#     [register_sha1_value(prop_values) for prop_values in property_values if prop_values.image_id < 0]
#
#     def assign_sha1_value(image_id, prop_value: PropertyValue):
#         image_index[image_id].properties[prop_value.property_id] = prop_value
#
#     # assign the sha1 bound property values to the images with corresponding sha1s
#     [assign_sha1_value(img.id, prop_value) for img in images if img.sha1 in sha1_properties for prop_value in
#      sha1_properties[img.sha1]]
#
#     [setattr(img, 'ahash', ahashs[img.sha1]) for img in images if img.sha1 in ahashs]
#     return images
#
#
# async def make_clusters(sensibility: float, sha1s: [str]) -> Clusters:
#     """
#     Compute clusters and return a list of lists of sha1
#     """
#     if not sha1s:
#         return []
#     values = await db.get_sha1_computed_values(sha1s)
#     clusters, distances = compute.make_clusters(values, method="kmeans", nb_clusters=sensibility)
#     return Clusters(clusters=clusters, distances=distances)
#
#
# async def get_similar_images(sha1s: list[str]):
#     vectors = [i.vector for i in await db.get_sha1_computed_values(sha1s)]
#     res = compute.get_similar_images(vectors)
#     return [img for img in res if img['sha1'] not in sha1s]
#
#
# async def add_property_to_images(property_id: int, sha1_list: list[str], value: JSON) -> str:
#     # first check that the property and the image exist:
#     images = await db.get_images(sha1s=sha1_list)
#     if await db.get_property_by_id(property_id) and images:
#         await db.set_property_values(image_ids=[img.id for img in images], property_id=property_id, value=value)
#         # check if a value already exists
#         # if await db.get_image_property(sha1, property_id):
#         #     await db.update_image_property(sha1, property_id, value)
#         # else:
#         #     await db.add_image_property(sha1, property_id, value)
#         return value
#     else:
#         raise HTTPException(status_code=400, detail="Trying to set a value on a non existent property or sha1")
#
#
# async def read_properties_file(data: pandas.DataFrame):
#     filenames, ids, sha1 = zip(*[(i.name, i.id, i.sha1) for i in await db.get_images()])
#
#     # if there are no duplicates them lets assume the props are sha1
#     if data.duplicated('key').sum() == 0:
#         prop_mode = "sha1"
#         matcher = dict(zip(filenames, sha1))
#     else:
#         prop_mode = "id"
#         matcher = dict(zip(filenames, ids))
#     data = data[data.key.isin(filenames)]
#     # data = data.drop_duplicates(subset='key', keep='first')
#     # add panoptic id or sha1 to the dataframe
#     data.loc[data.index, 'panoptic_id'] = data['key'].map(matcher)
#
#     # first, create new images where ids are the same
#     unique_ids = list(data.panoptic_id.unique())
#     clones_created = 0
#     # TODO: create clones all at once ? it's tricky with the ids to update
#     if prop_mode == "id":
#         for id_ in tqdm(unique_ids):
#             sub_data = data[data.panoptic_id == id_]
#             # create clones only if needed
#             if len(list(sub_data.panoptic_id)) == 0:
#                 continue
#             image = await db.get_images([id_])
#             image = image[0]
#             new_ids = await db.create_clones(image, sub_data.shape[0] - 1)
#             clones_created += len(new_ids)
#             data.loc[data.panoptic_id == id_, "panoptic_id"] = [image.id, *new_ids]
#         logging.getLogger('panoptic').info(f"created {clones_created} new images")
#     properties_to_create = data.columns.tolist()
#
#     # then for each property to create
#     for prop in properties_to_create:
#         if prop in ["key", "panoptic_id", "sha1"]:
#             continue
#
#         # create the property
#         prop_name, prop_type = prop.split('[')
#         prop_type = PropertyType(prop_type.split(']')[0])
#         property = await create_property(prop_name, prop_type, prop_mode)
#         # then get all possible values to insert
#         prop_values = list(data[prop].unique())
#
#         # if it's a tag property let's create the tags in the db
#         if property.id == PropertyType.tag or property.id == PropertyType.multi_tags:
#             tag_matcher = {}
#             # TODO: can we optimize to create all tags at once ?
#             for value in tqdm(prop_values):
#                 created_tags = []
#                 # if value is empty or empty quotes just create a "null" tag
#                 if pandas.isna(value) or str(value).strip() == "":
#                     value = "unknown"
#                 tags = [value] if property.id == PropertyType.tag else str(value).split(',')
#                 # if it's multi tag, assume tags are separated by a comma and create them separately
#                 for single_tag in tags:
#                     colors = range(11)
#                     color = random.randint(0, len(colors) - 1)
#                     parent_node = 0
#                     for child in single_tag.split('>'):
#                         tag = await create_tag(property.id, child, parent_node, color=color)
#                         parent_node = tag.id
#                         created_tags.append(tag.id)
#                 tag_matcher[value] = created_tags
#             # now change all values in the dataframe with the real value that we are going to insert
#             data.loc[data.index, prop] = data[prop].map(tag_matcher)
#         await db.set_multiple_property_values(property.id, list(data[prop]), list(data.panoptic_id))
#
#
# async def add_folder(folder):
#     found = await importer.import_folder(folder)
#     logging.info(f'found {found} images')
#     return folder
#
#
# new_images = []
#
#
# def get_new_images():
#     copy = [i for i in new_images]
#     new_images.clear()
#     return copy
#
#
# async def create_tag(property_id, value, parent_id, color: int) -> Tag:
#     existing_tag = await db.get_tag(property_id, value)
#     if existing_tag is not None:
#         if await db.tag_in_ancestors(existing_tag.id, parent_id):
#             raise HTTPException(status_code=400, detail="Adding a tag that is an ancestor of himself")
#         existing_tag.parents = list({*existing_tag.parents, parent_id})
#         await db.update_tag(existing_tag)
#         tag_id = existing_tag.id
#     else:
#         parents = [parent_id]
#         tag_id = await db.add_tag(property_id, value, json.dumps(parents), color)
#     return await db.get_tag_by_id(tag_id)
#
#
# async def tag_add_parent(tag_id, parent_id):
#     tag = await db.get_tag_by_id(tag_id)
#     parent = await db.get_tag_by_id(parent_id)
#     if tag is None:
#         raise HTTPException(status_code=400, detail=f"Tag: {tag_id} doesnt exist")
#     if parent is None:
#         raise HTTPException(status_code=400, detail=f"Parent Tag: {parent_id} doesnt exist")
#     if await db.tag_in_ancestors(tag.id, parent_id):
#         raise HTTPException(status_code=400, detail="Adding a tag that is an ancestor of himself")
#     tag.parents = list({*tag.parents, parent_id})
#     tag.color = parent.color
#     await db.update_tag(tag)
#     return tag
#
#
# async def update_tag(payload: UpdateTagPayload) -> Tag:
#     existing_tag = await db.get_tag_by_id(payload.id)
#     if not existing_tag:
#         raise HTTPException(status_code=400, detail="Trying to modify non existent tag")
#     # if await db.tag_in_ancestors(existing_tag.id, payload.parent_id):
#     #     raise HTTPException(status_code=400, detail="Adding a tag that is an ancestor of himself")
#     # change only fields of the tags that are set in the payload
#     # new_tag = existing_tag.copy(update=payload.dict(exclude_unset=True))
#     if payload.color is not None:
#         existing_tag.color = payload.color
#     if payload.value is not None:
#         existing_tag.value = payload.value
#
#     await db.update_tag(existing_tag)
#     return existing_tag
#
#
# async def delete_tag(tag_id: int) -> List[int]:
#     # first delete the tag
#     modified_tags = [await db.delete_tag_by_id(tag_id)]
#     # when deleting a tag, get all children of this tag
#     children = await db.get_tags_by_parent_id(tag_id)
#     # and remove parent ref of tag in children
#     [modified_tags.extend(await delete_tag_parent(c.id, tag_id)) for c in children]
#     # then get all images properties tagged with it
#     property_values = await db.get_property_values_with_tag(tag_id)
#     # and delete the tag ref from them
#     for data in property_values:
#         if tag_id in data.value:
#             data.value.remove(tag_id)
#             if data.image_id >= 0:
#                 await db.set_property_values(data.property_id, data.value, image_ids=[data.image_id])
#             else:
#                 await db.set_property_values(data.property_id, data.value, sha1s=[data.sha1])
#     return modified_tags
#
#
# async def delete_tag_parent(tag_id: int, parent_id: int) -> List[int]:
#     tag = await db.get_tag_by_id(tag_id)
#     tag.parents.remove(parent_id)
#     print(tag.parents)
#     color = random.randint(0, 11)
#     tag.color = color
#     print(color)
#     await db.update_tag(tag)
#     return tag
#
#
# async def get_tags(prop: str = None) -> Tags:
#     res = {}
#     tag_list = await db.get_tags(prop)
#     for tag in tag_list:
#         if tag.property_id not in res:
#             res[tag.property_id] = {}
#         res[tag.property_id][tag.id] = tag
#     return res
