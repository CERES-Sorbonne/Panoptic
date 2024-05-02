import json
from collections import defaultdict
from random import randint
from time import time
from typing import Any

from panoptic.core.db.db import Db
from panoptic.core.db.db_connection import DbConnection
from panoptic.core.project.project_events import ImportInstanceEvent
from panoptic.models import Property, PropertyUpdate, PropertyType, InstancePropertyValue, Instance, Tag, \
    TagUpdate, Vector, VectorDescription, ProjectVectorDescriptions, SetMode, \
    PropertyMode
from panoptic.models.computed_properties import computed_properties
from panoptic.models.results import DeleteTagResult
from panoptic.utils import convert_to_instance_values, clean_value, get_computed_values, is_circular


class ProjectDb:
    def __init__(self, conn: DbConnection):
        self._db = Db(conn)

        self.on_import_instance = ImportInstanceEvent()

    async def close(self):
        await self._db.close()

    def get_raw_db(self):
        return self._db

    # =====================================================
    # =================== Properties ======================
    # =====================================================

    async def add_property(self, name: str, property_type: PropertyType, mode='id') -> Property:
        return await self._db.add_property(name, property_type.value, mode)

    async def add_properties(self, properties: list[Property]):
        return await self._db.add_properties(properties)

    async def get_properties(self, no_computed=False) -> list[Property]:
        properties = await self._db.get_properties()
        if no_computed:
            return properties
        return [*properties, *computed_properties.values()]

    async def update_property(self, update: PropertyUpdate) -> Property:
        existing_property = await self._db.get_property(update.id)
        if not existing_property:
            raise Exception(f'Property {update.id} does not exist')
        new_property = existing_property.copy(update=update.dict(exclude_unset=True))
        await self._db.update_property(new_property)
        return new_property

    async def delete_property(self, property_id: str):
        await self._db.delete_property(property_id)

    # =====================================================
    # =============== Property Values =====================
    # =====================================================

    async def get_property_values(self, instances: list[Instance], property_ids: list[int] = None, no_computed=False) \
            -> list[InstancePropertyValue]:
        instance_ids = [i.id for i in instances]
        sha1s = list({img.sha1 for img in instances})
        instance_values = await self._db.get_instance_property_values(property_ids=property_ids,
                                                                      instance_ids=instance_ids)
        image_values = await self._db.get_image_property_values(property_ids=property_ids, sha1s=sha1s)
        converted_values = convert_to_instance_values(image_values, instances)

        computed_ids = [] if no_computed else computed_properties.keys()
        if computed_ids and property_ids:
            computed_ids = [pId for pId in property_ids if pId < 0]
        computed_values = [v for i in instances for v in get_computed_values(i, computed_ids)]
        return [*instance_values, *converted_values, *computed_values]

    async def set_property_values(self, property_id: int, instance_ids: list[int], value: Any):
        prop = await self._db.get_property(property_id)
        value = clean_value(prop, value)
        print(property_id, value)
        if prop.mode == PropertyMode.id:
            # print('mode id')
            if value is None:
                await self._db.delete_instance_property_value(property_id, instance_ids)
            else:
                await self._db.set_instance_property_value(property_id, instance_ids, value)
        if prop.mode == PropertyMode.sha1:
            # print('mode sha1')
            instances = await self._db.get_instances(ids=instance_ids)
            sha1s = {i.sha1 for i in instances}
            if value is None:
                await self._db.delete_image_property_value(property_id, list(sha1s))
            else:
                await self._db.set_image_property_value(property_id, list(sha1s), value)

        return [InstancePropertyValue(property_id=property_id, instance_id=i, value=value) for i in instance_ids]

    async def set_property_values_array(self, property_id: int, instance_ids: list[int], values: list[Any]):
        prop = await self._db.get_property(property_id)
        values = [clean_value(prop, v) for v in values]
        pairs = [(i, v) for i, v in zip(instance_ids, values)]
        to_delete = [p for p in pairs if p[1] is None]
        to_update = [p for p in pairs if p[1] is not None]
        if prop.mode == PropertyMode.id:
            if to_update:
                ids = [v[0] for v in to_update]
                vals = [v[1] for v in to_update]
                await self._db.set_instance_property_array_values(property_id=prop.id, instance_ids=ids, values=vals)
            if to_delete:
                ids = [v[0] for v in to_delete]
                await self._db.delete_instance_property_value(property_id=prop.id, instance_ids=ids)
        if prop.mode == PropertyMode.sha1:
            if to_update:
                ids = [v[0] for v in to_update]
                instances = await self._db.get_instances(ids=ids)
                index = {i.id: i.sha1 for i in instances}
                sha1_pairs = [(index[v[0]], v[1]) for v in to_update]
                sha1s = [p[0] for p in sha1_pairs]
                vals = [p[1] for p in sha1_pairs]
                await self._db.set_image_property_array_values(property_id=prop.id, sha1s=sha1s, values=vals)
            if to_delete:
                ids = [v[0] for v in to_delete]
                instances = await self._db.get_instances(ids=ids)
                sha1s = list({i.sha1 for i in instances})
                await self._db.delete_image_property_value(property_id=prop.id, sha1s=sha1s)
        return [InstancePropertyValue(property_id=property_id, instance_id=p[0], value=p[1]) for p in pairs]

    async def set_tag_property_value(self, property_id: int, instance_ids: list[int], value: list[int], mode: SetMode):
        if mode == SetMode.set:
            return await self.set_property_values(property_id=property_id, instance_ids=instance_ids, value=value)

        instances = await self.get_instances_with_properties(instance_ids=instance_ids, property_ids=[property_id])

        to_set = [i for i in instances if property_id not in i.properties]
        if to_set:
            set_res = await self.set_property_values(property_id=property_id, instance_ids=[i.id for i in to_set],
                                                     value=value)
        else:
            set_res = []
        if mode == SetMode.add:
            to_add = [i for i in instances if property_id in i.properties]
            ids = [i.id for i in to_add]
            vals = [[*i.properties[property_id].value, *value] for i in to_add]
            vals = [[*{*v}] for v in vals]
            res_add = await self.set_property_values_array(property_id=property_id, instance_ids=ids, values=vals)
            return [*set_res, *res_add]

        if mode == SetMode.delete:
            to_del = [i for i in instances if property_id in i.properties]
            ids = [i.id for i in to_del]
            vals = [[v for v in i.properties[property_id].value if v not in value] for i in to_del]
            res_del = await self.set_property_values_array(property_id=property_id, instance_ids=ids, values=vals)
            return [*set_res, *res_del]

    async def add_property_tag_values(self, property_id: int, instance_ids: list[int], values: list[list[int]]):
        pass

    # =====================================================
    # =================== Instances =======================
    # =====================================================

    async def add_instance(self, folder_id: int, name: str, extension: str, sha1: str, url: str, width: int,
                           height: int, ahash: str):
        res = await self._db.add_instance(folder_id, name, extension, sha1, url, width, height, ahash)
        self.on_import_instance.emit(res)

    async def add_instances(self, instances: list[Instance]):
        return await self._db.add_instances(instances)

    async def get_instances(self, ids: list[int] = None, sha1s: list[str] = None):
        images = await self._db.get_instances(ids=ids, sha1s=sha1s)
        return images

    async def get_instances_with_properties(self, instance_ids: list[int] = None, property_ids: list[int] = None) \
            -> list[Instance]:
        instances = await self._db.get_instances(instance_ids)
        instance_values = await self.get_property_values(instances=instances, property_ids=property_ids)
        instance_index: dict[int, Instance] = {i.id: i for i in instances}
        [instance_index[v.instance_id].properties.update({v.property_id: v}) for v in instance_values]

        return instances

    async def empty_or_clone(self, paths: list[str]) -> list[Instance]:
        instances = await self.get_instances()
        path_to_instances = defaultdict(list)
        res: list[Instance] = []
        for i in instances:
            path_to_instances[i.url].append(i)
        for path in paths:
            if not path_to_instances[path]:
                raise Exception('{path} is not already imported in panoptic. '
                                'Impossible to import the data before importing the file')
            matches = sorted(path_to_instances[path], key=lambda x: x.id)
            values = await self.get_property_values(instances=[matches[0]], no_computed=True)
            if not values:
                res.append(matches[0])
            else:
                new_instance = await self._db.clone_instance(matches[0])
                res.append(new_instance)
        return res

    async def test_empty(self, instance_ids: list[int]):
        res = await self._db.count_instance_values(instance_ids)
        return set([i for i in instance_ids if i not in res])

    # ========== Tags ==========
    async def get_tags(self, prop: int = None) -> list[Tag]:
        tag_list = await self._db.get_tags(prop)
        return tag_list

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

    async def add_tags(self, tags: list[Tag]) -> list[Tag]:
        new_tags = await self._db.add_tags(tags)
        if len(new_tags) != len(tags):
            raise Exception('Failed to add all tags. Unexpected Behavior')
        fake_to_id = {t.id: new_t.id for t, new_t in zip(tags, new_tags)}

        def correct(tid: int):
            return fake_to_id[tid] if tid in fake_to_id else tid

        for t, new_t in zip(tags, new_tags):
            new_t.parents = [correct(p) for p in t.parents]

        await self.set_tags_parents([(t.id, t.parents) for t in new_tags])

        return new_tags

    async def set_tags_parents(self, links: list[tuple[int, list[int]]]):
        tree = await self.get_tag_tree()
        for i in range(len(links)):
            child, parents = links[i]
            valid_parents = []
            for parent in parents:
                if is_circular(tree, (child, parent)):
                    continue
                valid_parents.append(parent)
                tree[child].add(parent)
            links[i] = (child, valid_parents)

        await self._db.set_tags_parents(links)



    async def get_tag_tree(self):
        tags = await self.get_tags()
        tree: dict[int, set[int]] = {t.id: set(t.parents) for t in tags}
        return tree

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

    async def delete_tag(self, tag_id: int):
        tag = await self._db.get_tag_by_id(tag_id)
        instances = await self._db.get_instances()
        values = await self.get_property_values(instances, [tag.property_id])

        to_update = [v for v in values if tag_id in v.value]
        [v.value.remove(tag_id) for v in to_update if tag_id in v.value]

        ids = [v.instance_id for v in to_update]
        vals = [v.value for v in to_update]
        await self.set_property_values_array(tag.property_id, ids, vals)

        tags = await self._db.get_tags(tag.property_id)
        updated_tags = [t for t in tags if tag_id in t.parents]
        [t.parents.remove(tag_id) for t in updated_tags]
        [await self._db.update_tag(t) for t in updated_tags]

        await self._db.delete_tag_by_id(tag_id)
        # print(to_update, updated_tags)
        return DeleteTagResult(tag_id=tag.property_id, updated_values=to_update, updated_tags=updated_tags)

    async def delete_tag_parent(self, tag_id: int, parent_id: int) -> list[int]:
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
    async def get_vectors(self, source: str, type_: str, sha1s: list[str] = None):
        return await self._db.get_vectors(source, type_, sha1s)

    async def get_default_vectors(self, sha1s: list[str] = None):
        default = await self._db.get_default_db_vector_id()
        if not default:
            raise Exception('No default vectors set. Make sure vectors are computed')
        source, type_ = default.split('.')
        return await self._db.get_vectors(source, type_, sha1s)

    async def add_vector(self, vector: Vector):
        return await self._db.add_vector(vector)

    async def vector_exist(self, source: str, type_: str, sha1: str) -> bool:
        return await self._db.vector_exist(source, type_, sha1)

    async def set_default_vectors(self, vector: VectorDescription):
        await self._db.set_default_vector_id(vector_id=vector.id)

    async def get_vectors_info(self):
        vectors = await self._db.get_vector_descriptions()
        default = await self._db.get_default_db_vector_id()
        return ProjectVectorDescriptions(vectors=vectors, default_vectors=default)

    async def get_ui_data(self, key: str):
        return await self._db.get_ui_data(key)

    async def get_all_ui_data(self):
        return await self._db.get_all_ui_data()

    async def set_ui_data(self, key: str, value: Any):
        return await self._db.set_ui_data(key, value)

    async def get_plugin_data(self, key: str):
        return await self._db.get_plugin_data(key)

    async def set_plugin_data(self, key: str, value: Any):
        return await self._db.set_plugin_data(key, value)
