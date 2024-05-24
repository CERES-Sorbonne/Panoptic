from collections import defaultdict
from random import randint
from typing import Any

from panoptic.core.db.db import Db
from panoptic.core.db.db_connection import DbConnection
from panoptic.core.project.project_events import ImportInstanceEvent
from panoptic.models import Property, PropertyType, InstancePropertyValue, Instance, Tag, \
    Vector, VectorDescription, ProjectVectorDescriptions, PropertyMode
from panoptic.models.computed_properties import computed_properties
from panoptic.utils import convert_to_instance_values, get_computed_values, get_all_parent, clean_and_separate_values


class ProjectDb:
    def __init__(self, conn: DbConnection):
        self._db = Db(conn)
        self._fake_id_counter = -100

        self.on_import_instance = ImportInstanceEvent()

    async def close(self):
        await self._db.close()

    def get_raw_db(self):
        return self._db

    def _get_fake_id(self):
        self._fake_id_counter -= 1
        return self._fake_id_counter

    # =====================================================
    # =================== Properties ======================
    # =====================================================

    def create_property(self, name: str, type_: PropertyType, mode: PropertyMode) -> Property:
        return Property(id=self._get_fake_id(), name=name, type=type_, mode=mode)

    async def get_properties(self, computed=False) -> list[Property]:
        properties = await self._db.get_properties()
        if not computed:
            return properties
        return [*properties, *computed_properties.values()]

    async def delete_property(self, property_id: int):
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

    # =====================================================
    # =================== Instances =======================
    # =====================================================

    def create_instance(self, folder_id: int, name: str, extension: str, sha1: str, url: str, width: int,
                        height: int, ahash: str):
        return Instance(id=self._get_fake_id(), folder_id=folder_id, name=name, extension=extension, sha1=sha1, url=url,
                        height=height, width=width, ahash=ahash)

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

    async def test_empty(self, instance_ids: list[int]):
        res = await self._db.count_instance_values(instance_ids)
        return set([i for i in instance_ids if i not in res])

    # ========== Tags ==========

    def create_tag(self, property_id: int, value: str, parent_ids: list[int] = None, color=-1):
        if parent_ids is None:
            parent_ids = []
        if color < 0:
            color = randint(0, 11)
        return Tag(id=self._get_fake_id(), property_id=property_id, value=value, parents=parent_ids, color=color)

    async def get_tags(self, prop: int = None) -> list[Tag]:
        tag_list = await self._db.get_tags(prop)
        return tag_list

    async def get_tags_by_ids(self, ids: list[int]):
        return await self._db.get_tags_by_ids(ids)

    async def delete_tags(self, ids: list[int]):
        to_delete = set(ids)
        db_tags = await self.get_tags()
        remain = [t for t in db_tags if t.id not in to_delete]
        updated_tags = [t for t in remain if any([pId in to_delete for pId in t.parents])]
        for t in updated_tags:
            t.parents = [pId for pId in t.parents if pId not in to_delete]

        property_ids = list({t.property_id for t in db_tags})

        def remove_tag(value):
            value.value = [v for v in value.value if v not in to_delete]

        instance_values = await self._db.get_instance_property_values(property_ids=property_ids)
        updated_instance_values = [v for v in instance_values if any(tId in to_delete for tId in v.value)]
        [remove_tag(v) for v in updated_instance_values]

        image_values = await self._db.get_image_property_values(property_ids=property_ids)
        updated_image_values = [v for v in image_values if any(tId in to_delete for tId in v.value)]
        [remove_tag(v) for v in updated_image_values]

        await self._db.import_tags(updated_tags)

        props = {p.id: p for p in await self._db.get_properties()}
        valid, empty_instance_values = clean_and_separate_values(instance_values, props)
        if valid:
            await self._db.import_instance_property_values(valid)
        if empty_instance_values:
            await self._db.delete_instance_property_values(empty_instance_values)

        valid, empty_image_values = clean_and_separate_values(image_values, props)
        if valid:
            await self._db.import_image_property_values(valid)
        if empty_image_values:
            await self._db.delete_image_property_values(empty_image_values)

        for i in to_delete:
            await self._db.delete_tag_by_id(i)

        return updated_tags, updated_instance_values, updated_image_values, empty_instance_values, empty_image_values

    async def verify_tags(self, tags: list[Tag]):
        for tag in tags:
            if tag.parents is None:
                tag.parents = []
            if tag.color < 0 or tag.color is None:
                tag.color = randint(0, 11)
        tag_groups: dict[int, list[Tag]] = defaultdict(list)
        [tag_groups[t.property_id].append(t) for t in tags]
        for propId in tag_groups:
            tags = tag_groups[propId]
            tag_index: dict[int, Tag] = {t.id: t for t in await self.get_tags(propId)}
            updated_tags = [t for t in tags if t.id in tag_index]
            new_tags = [t for t in tags if t.id not in tag_index]
            for tag in new_tags:
                tag_index[tag.id] = tag
            for tag in updated_tags:
                parents = list(*tag.parents)
                for parent_id in parents:
                    all_parents = get_all_parent(tag_index[parent_id], tag_index)
                    if tag.id in all_parents:
                        tag.parents.remove(parent_id)

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
