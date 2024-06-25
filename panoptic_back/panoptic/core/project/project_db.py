from collections import defaultdict
from random import randint
from typing import Any

from panoptic.core.db.db import Db
from panoptic.core.db.db_connection import DbConnection
from panoptic.core.project.project_events import ImportInstanceEvent
from panoptic.models import Property, PropertyType, InstanceProperty, Instance, Tag, \
    Vector, VectorDescription, ProjectVectorDescriptions, PropertyMode, DbCommit, ImageProperty
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

    async def get_properties(self, ids: list[int] = None, computed=False) -> list[Property]:
        properties = await self._db.get_properties(ids)
        if not computed:
            return properties
        return [*properties, *computed_properties.values()]

    # =====================================================
    # =============== Property Values =====================
    # =====================================================

    async def get_property_values(self, instances: list[Instance], property_ids: list[int] = None, no_computed=False) \
            -> list[InstanceProperty]:
        instance_ids = [i.id for i in instances]
        sha1s = list({img.sha1 for img in instances})
        instance_values = await self._db.get_instance_property_values(property_ids=property_ids,
                                                                      instance_ids=instance_ids)
        image_values = await self._db.get_image_property_values(property_ids=property_ids, sha1s=sha1s)
        converted_values = convert_to_instance_values(image_values, instances)

        computed_values = [v for i in instances for v in get_computed_values(i)]
        return [*instance_values, *converted_values, *computed_values]

    async def get_instance_property_values(self, property_ids: list[int] = None, instance_ids: list[int] = None) \
            -> list[InstanceProperty]:
        res = await self._db.get_instance_property_values(property_ids, instance_ids)
        return res

    async def get_image_property_values(self, property_ids: list[int] = None, sha1s: list[str] = None) \
            -> list[ImageProperty]:
        res = await self._db.get_image_property_values(property_ids, sha1s)
        return res

    @staticmethod
    def get_computed_values(instances: list[Instance]):
        computed_values = [v for i in instances for v in get_computed_values(i)]
        return computed_values
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

    async def get_tags2(self, ids: list[int], property_ids: list[int]):
        if not ids and not property_ids:
            return await self._db.get_tags()
        if ids:
            return await self._db.get_tags_by_ids(ids)

        res = []
        for prop_id in property_ids:
            res.extend(await self._db.get_tags(prop_id))
        return res


    async def _delete_tags(self, ids: list[int]):
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

    async def _verify_tags(self, tags: list[Tag]):
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
                parents = list(tag.parents)
                for parent_id in parents:
                    if parent_id == 0:
                        continue
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

    async def delete_folder(self, folder_id: int):
        return await self._db.delete_folder(folder_id)

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

    async def apply_commit(self, commit: DbCommit):
        inverse = DbCommit()
        inverse.timestamp = commit.timestamp

        instance_id_map: dict[int, int] = {}
        property_id_map: dict[int, int] = {}
        tag_id_map: dict[int, int] = {}

        properties = {p.id: p for p in await self._db.get_properties()}
        # add new properties to index
        if commit.properties:
            for p in commit.properties:
                properties[p.id] = p

        if commit.instance_values:
            valid, empty = clean_and_separate_values(commit.instance_values, properties)
            commit.empty_instance_values.extend(empty)
            commit.instance_values = valid

        if commit.image_values:
            valid, empty = clean_and_separate_values(commit.image_values, properties)
            commit.empty_image_values.extend(empty)
            commit.image_values = valid

        if commit.instances:
            ids = [i.id for i in commit.instances]
            current = await self._db.get_instances(ids=ids)
            db_instances = await self._db.import_instances(commit.instances)
            instance_id_map = {old: new.id for old, new in zip(ids, db_instances)}

            current_ids = {i.id for i in current}
            inverse.empty_instances.extend([i.id for i in db_instances if i.id not in current_ids])
            inverse.instances.extend(current)

        if commit.properties:
            ids = [p.id for p in commit.properties]
            current = await self._db.get_properties(ids=ids)
            db_properties = await self._db.import_properties(commit.properties)
            property_id_map = {old: new.id for old, new in zip(ids, db_properties)}

            current_ids = {p.id for p in current}
            inverse.empty_properties.extend([p.id for p in db_properties if p.id not in current_ids])
            inverse.properties.extend(current)

        if commit.tags:
            ids = [t.id for t in commit.tags]
            current = await self._db.get_tags_by_ids(ids=ids)
            for tag in commit.tags:
                if tag.property_id in property_id_map:
                    tag.property_id = property_id_map[tag.property_id]
            await self._verify_tags(commit.tags)
            db_tags = await self._db.import_tags(commit.tags)
            tag_id_map = {old: new.id for old, new in zip(ids, db_tags)}

            current_ids = {tt.id for tt in current}
            inverse.empty_tags.extend([t.id for t in db_tags if t.id not in current_ids])
            inverse.tags.extend(current)

        def correct_property_id(value: InstanceProperty | ImageProperty):
            if value.property_id in property_id_map:
                value.property_id = property_id_map[value.property_id]

        def correct_instance_id(value: InstanceProperty):
            if value.instance_id in instance_id_map:
                value.instance_id = instance_id_map[value.instance_id]

        def correct_tag_id(value: InstanceProperty | ImageProperty):
            if isinstance(value.value, list):
                value.value = [tId if tId not in tag_id_map else tag_id_map[tId] for tId in value.value]

        if commit.instance_values:
            [correct_property_id(v) for v in commit.instance_values]
            [correct_instance_id(v) for v in commit.instance_values]
            [correct_tag_id(v) for v in commit.instance_values]

            current = await self._db.get_instance_property_values_from_keys(commit.instance_values)
            existing = {}
            for v in current:
                if v.property_id not in existing:
                    existing[v.property_id] = {}
                existing[v.property_id][v.instance_id] = True
            await self._db.import_instance_property_values(commit.instance_values)

            missing_ids = [v for v in commit.instance_values
                           if v.property_id not in existing or v.instance_id not in existing[v.property_id]]
            inverse.empty_instance_values.extend(missing_ids)
            inverse.instance_values.extend(current)

        if commit.image_values:
            [correct_property_id(v) for v in commit.image_values]
            [correct_tag_id(v) for v in commit.image_values]

            current = await self._db.get_image_property_values_from_keys(commit.image_values)
            existing = {}
            for v in current:
                if v.property_id not in existing:
                    existing[v.property_id] = {}
                existing[v.property_id][v.sha1] = True
            await self._db.import_image_property_values(commit.image_values)

            missing_ids = [v for v in commit.image_values
                           if v.property_id not in existing or v.sha1 not in existing[v.property_id]]
            inverse.empty_image_values.extend(missing_ids)
            inverse.image_values.extend(current)

        if commit.empty_image_values:
            current = await self._db.get_image_property_values_from_keys(commit.empty_image_values)
            inverse.image_values.extend(current)
            await self._db.delete_image_property_values(commit.empty_image_values)

        if commit.empty_instance_values:
            current = await self._db.get_instance_property_values_from_keys(commit.empty_instance_values)
            inverse.instance_values.extend(current)
            await self._db.delete_instance_property_values(commit.empty_instance_values)
        if commit.empty_tags:
            current = await self._db.get_tags_by_ids(commit.empty_tags)
            inverse.tags.extend(current)
            tags, instance_values, image_values, empty_inst, empty_img = await self._delete_tags(commit.empty_tags)
            commit.tags.extend(tags)
            commit.instance_values.extend(instance_values)
            commit.image_values.extend(image_values)
            commit.empty_instance_values.extend(empty_inst)
            commit.empty_image_values.extend(empty_img)

        if commit.empty_properties:
            current = await self._db.get_properties()
            inverse.properties.extend([p for p in current if p.id in commit.empty_properties])
            [await self._db.delete_property(pid) for pid in commit.empty_properties]

        if commit.empty_instances:
            current = await self._db.get_instances(ids=commit.empty_instances)
            inverse.instances.extend(current)
            # TODO: or not to do ?
            # await self._db.delete_instance(ids=commit.empty_instances)
        return inverse
