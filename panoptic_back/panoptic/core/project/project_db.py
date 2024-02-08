import json
from random import randint
from typing import Any, List, Dict

from panoptic.core.db.db import Db
from panoptic.core.db.db_connection import DbConnection
from panoptic.core.project.project_events import ImportInstanceEvent
from panoptic.models import Property, PropertyUpdate, PropertyType, PropertyValue, Instance, Tags, Tag, \
    TagUpdate, Vector, PluginDefaultParams, VectorDescription, ActionParam, ProjectVectorDescriptions


class ProjectDb:
    def __init__(self, conn: DbConnection):
        self._db = Db(conn)

        self.on_import_instance = ImportInstanceEvent()

    def get_raw_db(self):
        return self._db

    # ========== Properties ==========
    async def get_properties(self) -> Dict[int, Property]:
        properties = await self._db.get_properties()
        return {prop.id: prop for prop in properties}

    async def add_property(self, name: str, property_type: PropertyType, mode='id') -> Property:
        return await self._db.add_property(name, property_type.value, mode)

    async def update_property(self, update: PropertyUpdate) -> Property:
        existing_property = await self._db.get_property_by_id(update.id)
        if not existing_property:
            raise Exception(f'Property {update.id} does not exist')
        new_property = existing_property.copy(update=update.dict(exclude_unset=True))
        await self._db.update_property(new_property)
        return new_property

    async def delete_property(self, property_id: str):
        await self._db.delete_property(property_id)

    async def set_property_values(self, property_id: int, value: Any, image_ids: List[int] = None,
                                  sha1s: List[int] = None):
        if image_ids and sha1s:
            raise TypeError('Only image_ids or sha1s should be given as keys. Never both')

        prop = await self._db.get_property_by_id(property_id)
        if prop.mode == 'id' and not image_ids:
            raise TypeError(f'Property {property_id}: {prop.name} needs image ids as key [mode: {prop.mode}]')
        if prop.mode == 'sha1' and not sha1s:
            raise TypeError(f'Property {property_id}: {prop.name} needs sha1s as key [mode: {prop.mode}]')

        if prop.id == PropertyType.tag or prop.id == PropertyType.multi_tags:
            if value and not isinstance(value, list):
                value = [int(value)]

        if prop.id == PropertyType.checkbox:
            value = True if value == 'true' or value is True else False

        return await self._db.set_property_values(property_id, value, image_ids, sha1s)

    async def delete_property_values(self, property_id: int, image_ids: List[int] = None, sha1s: List[int] = None):
        return await self._db.delete_property_value(property_id, image_ids, sha1s)

    async def add_property_values(self, property_id: int, value: Any, image_ids: List[int] = None,
                                  sha1s: List[int] = None):
        if image_ids and sha1s:
            raise TypeError('Only image_ids or sha1s should be given as keys. Never both')

        prop = await self._db.get_property_by_id(property_id)
        if prop.mode == 'id' and not image_ids:
            raise TypeError(f'Property {property_id}: {prop.name} needs image ids as key [mode: {prop.mode}]')
        if prop.mode == 'sha1' and not sha1s:
            raise TypeError(f'Property {property_id}: {prop.name} needs sha1s as key [mode: {prop.mode}]')

        if prop.id != PropertyType.multi_tags:
            raise TypeError('add_property_values is only supported for multi_tag properties')

        if value and not isinstance(value, list):
            value = [int(value)]

        current_values = await self._db.get_property_values(property_ids=[property_id], image_ids=image_ids,
                                                            sha1s=sha1s)
        if image_ids:
            value_index = {v.image_id: v.value for v in current_values}
            [value_index.update({id_: []}) for id_ in image_ids if id_ not in value_index]
            [value_index[id_].extend(value) for id_ in image_ids]
            values = [list(set(value_index[id_])) for id_ in image_ids]
            await self._db.set_multiple_property_values(property_id, values, image_ids)
        else:
            value_index = {v.sha1: v.value for v in current_values}
            [value_index.update({sha1: []}) for sha1 in sha1s if sha1 not in value_index]
            [value_index[sha1].extend(value) for sha1 in sha1s]
            values = [list(set(value_index[sha1])) for sha1 in sha1s]
            await self._db.set_multiple_property_values(property_id, values, sha1s)

        updated_ids = image_ids
        if not image_ids:
            images = await self._db.get_instances(sha1s=sha1s)
            updated_ids = [img.id for img in images]
        return updated_ids, value

    # ========== Instances / Images ==========
    async def get_instances(self, ids: List[int] = None):
        images = await self._db.get_instances(ids=ids)
        return images

    async def get_instances_with_properties(self, ids: List[int] = None, properties: List[int] = None) -> List[
        Instance]:
        images = await self._db.get_instances(ids)
        sha1s = list({img.sha1 for img in images})
        # get ids bound property values
        property_values = await self._db.get_property_values(property_ids=properties, image_ids=ids)

        # get sha1 bound property values when image_ids is set and therefore property_values only return id bound
        # properties
        if ids:
            sha1s_values = await self._db.get_property_values(sha1s=sha1s)
            property_values += sha1s_values

        image_index = {img.id: img for img in images}

        def assign_value(prop_value):
            image_index[prop_value.image_id].properties[prop_value.property_id] = prop_value

        # fill the index with ids bound property values
        [assign_value(prop_value) for prop_value in property_values if prop_value.image_id >= 0]

        sha1_properties = {}

        def register_sha1_value(prop_value: PropertyValue):
            if prop_value.sha1 not in sha1_properties:
                sha1_properties[prop_value.sha1] = []
            sha1_properties[prop_value.sha1].append(prop_value)

        # populate the index of sha1 properties with prop_values that are bound to sha1s
        [register_sha1_value(prop_values) for prop_values in property_values if prop_values.image_id < 0]

        def assign_sha1_value(image_id, prop_value: PropertyValue):
            image_index[image_id].properties[prop_value.property_id] = prop_value

        # assign the sha1 bound property values to the images with corresponding sha1s
        [assign_sha1_value(img.id, prop_value) for img in images if img.sha1 in sha1_properties for prop_value in
         sha1_properties[img.sha1]]

        return images

    async def add_instance(self, folder_id: int, name: str, extension: str, sha1: str, url: str, width: int,
                           height: int, ahash: str):
        res = await self._db.add_image(folder_id, name, extension, sha1, url, width, height, ahash)
        self.on_import_instance.emit(res)

    # ========== Tags ==========
    async def get_tags(self, prop: int = None) -> Tags:
        res = {}
        tag_list = await self._db.get_tags(prop)
        for tag in tag_list:
            if tag.property_id not in res:
                res[tag.property_id] = {}
            res[tag.property_id][tag.id] = tag
        return res

    async def add_tag(self, property_id, value, parent_id, color: int) -> Tag:
        existing_tag = await self._db.get_tag(property_id, value)
        if existing_tag is not None:
            if await self._db.tag_in_ancestors(existing_tag.id, parent_id):
                raise Exception("Adding a tag that is an ancestor of himself")
            existing_tag.parents = list({*existing_tag.parents, parent_id})
            await self._db.update_tag(existing_tag)
            tag_id = existing_tag.id
        else:
            parents = [parent_id]
            tag_id = await self._db.add_tag(property_id, value, json.dumps(parents), color)
        return await self._db.get_tag_by_id(tag_id)

    async def add_tag_parent(self, tag_id, parent_id):
        tag = await self._db.get_tag_by_id(tag_id)
        parent = await self._db.get_tag_by_id(parent_id)
        if tag is None:
            raise Exception(f"Tag: {tag_id} doesnt exist")
        if parent is None:
            raise Exception(f"Parent Tag: {parent_id} doesnt exist")
        if await self._db.tag_in_ancestors(tag.id, parent_id):
            raise Exception("Adding a tag that is an ancestor of himself")
        tag.parents = list({*tag.parents, parent_id})
        tag.color = parent.color
        await self._db.update_tag(tag)
        return tag

    async def update_tag(self, update: TagUpdate) -> Tag:
        existing_tag = await self._db.get_tag_by_id(update.id)
        if not existing_tag:
            raise Exception("Trying to modify non existent tag")
        if update.color is not None:
            existing_tag.color = update.color
        if update.value is not None:
            existing_tag.value = update.value
        await self._db.update_tag(existing_tag)
        return existing_tag

    async def delete_tag(self, tag_id: int) -> List[int]:
        modified_tags = [await self._db.delete_tag_by_id(tag_id)]
        children = await self._db.get_tags_by_parent_id(tag_id)
        [modified_tags.extend(await self.delete_tag_parent(c.id, tag_id)) for c in children]
        property_values = await self._db.get_property_values_with_tag(tag_id)
        for data in property_values:
            if tag_id in data.value:
                data.value.remove(tag_id)
                if data.image_id >= 0:
                    await self._db.set_property_values(data.property_id, data.value, image_ids=[data.image_id])
                else:
                    await self._db.set_property_values(data.property_id, data.value, sha1s=[data.sha1])
        return modified_tags

    async def delete_tag_parent(self, tag_id: int, parent_id: int) -> List[int]:
        tag = await self._db.get_tag_by_id(tag_id)
        tag.parents.remove(parent_id)
        color = randint(0, 11)
        tag.color = color
        await self._db.update_tag(tag)
        return tag

    # =========== Folders ===========
    async def add_folder(self, path: str, name: str, parent: int = None):
        return await self._db.add_folder(path, name, parent)

    async def get_folders(self):
        return await self._db.get_folders()

    async def get_folder(self, folder_id: int):
        return await self._db.get_folder(folder_id)

    # =========== Vectors ===========
    async def get_vectors(self, source: str, type_: str, sha1s: List[str] = None):
        return await self._db.get_vectors(source, type_, sha1s)

    async def get_default_vectors(self, sha1s: List[str] = None):
        default = await self._db.get_action_param('get_vectors')
        if not default:
            raise Exception('No default vectors set. Make sure vectors are computed')
        default = VectorDescription(**json.loads(default.value))
        return await self._db.get_vectors(default.source, default.type, sha1s)

    async def add_vector(self, vector: Vector):
        return await self._db.add_vector(vector)

    async def vector_exist(self, source: str, type_: str, sha1: str) -> bool:
        return await self._db.vector_exist(source, type_, sha1)

    async def set_default_vectors(self, vector: VectorDescription):
        await self._db.set_action_param(ActionParam(name='get_vectors', value=json.dumps(vector.json())))

    async def get_vectors_info(self):
        vectors = await self._db.get_vector_descriptions()
        default = await self._db.get_action_param('get_vectors')
        if default:
            default = VectorDescription(**json.loads(default.value))
        return ProjectVectorDescriptions(vectors=vectors, default_vectors=default)

    # ============ Plugins =============
    async def set_plugin_default_params(self, params: PluginDefaultParams):
        return await self._db.set_plugin_default_params(params)
