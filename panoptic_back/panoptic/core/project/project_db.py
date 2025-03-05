from random import randint
from typing import Any

from panoptic.core.db.db import Db
from panoptic.core.db.db_connection import DbConnection
from panoptic.core.db.utils import safe_update_tag_parents, verify_tag_color
from panoptic.core.project.project_events import ImportInstanceEvent
from panoptic.core.project.undo_queue import UndoQueue
from panoptic.models import Property, PropertyType, InstanceProperty, Instance, Tag, \
    Vector, VectorDescription, ProjectVectorDescriptions, PropertyMode, DbCommit, ImageProperty, DeleteFolderConfirm, \
    ImagePropertyKey, InstancePropertyKey
from panoptic.models.computed_properties import computed_properties
from panoptic.utils import convert_to_instance_values, get_computed_values, clean_and_separate_values, separate_ids


class ProjectDb:
    def __init__(self, conn: DbConnection):
        self._db = Db(conn)
        self._fake_id_counter = -100
        self.undo_queue = UndoQueue(self)
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
    # ================= Property Groups ===================
    # =====================================================

    async def get_property_groups(self):
        return await self._db.get_property_groups()

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

    # async def stream_instance_property_values(self, chunk_size: int):
    #     cursor = 0
    #     cont = True  # continue
    #     while cont:
    #         chunk = await self._db.stream_instance_property_values(cursor, chunk_size)
    #         if len(chunk) < chunk_size:
    #             cont = False
    #         cursor += len(chunk)

    async def stream_instance_property_values(self, position: int, chunk_size: int):
        res = await self._db.stream_instance_property_values(position, chunk_size)
        return res, len(res) < chunk_size

    async def stream_image_property_values(self, position: int, chunk_size: int):
        res = await self._db.stream_image_property_values(position, chunk_size)
        return res, len(res) < chunk_size

    @staticmethod
    def get_computed_values(instances: list[Instance]):
        computed_values = [v for i in instances for v in get_computed_values(i)]
        return computed_values

    # =====================================================
    # ==================== Images =========================
    # =====================================================

    async def import_image(self, sha1: str, small: bytes, medium: bytes, large: bytes):
        return await self._db.import_image(sha1, small, medium, large)

    async def get_small_image(self, sha1: str):
        return await self._db.get_small_image(sha1)

    async def get_medium_image(self, sha1: str):
        return await self._db.get_medium_image(sha1)

    async def get_large_image(self, sha1: str):
        return await self._db.get_large_image(sha1)

    async def has_image(self, sha1: str):
        return await self._db.has_image(sha1)

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

    async def stream_instances(self, position: int, chunk_size: int):
        res = await self._db.stream_instances(position, chunk_size)
        return res, len(res) < chunk_size

    async def test_empty(self, instance_ids: list[int]):
        res = await self._db.count_instance_values(instance_ids)
        return set([i for i in instance_ids if i not in res])

    async def get_all_instances_ids(self):
        return await self._db.get_all_instances_ids()

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

    async def merge_tags(self, tag_ids: list[int]):
        tags = await self._db.get_tags_by_ids(tag_ids)
        main_tag = [t for t in tags if t.id == tag_ids[0]][0]
        prop_id = main_tag.property_id
        if not len(tag_ids) >= 2:
            raise ValueError('Tag merge failed. Select at least 2 tags')
        if not all([t.property_id == prop_id for t in tags]):
            raise ValueError('Tag merge failed. All tags must come from the same property')

        commit = DbCommit()
        tag_set = set(tag_ids)
        removed_set = set(tag_ids[1:])

        all_tags = await self.get_tags(prop_id)
        main_tag.parents = list(set([p for t in tags for p in t.parents if p not in removed_set and p != main_tag.id]))
        tags_to_update = [t for t in all_tags if any([p in removed_set for p in
                                                      t.parents]) and t.id not in removed_set and t.id != main_tag.id]
        for tag in tags_to_update:
            corrected_parents = []
            has_main_tag = False
            for parent_id in tag.parents:
                if parent_id not in removed_set and parent_id != main_tag.id:
                    corrected_parents.append(parent_id)
                elif not has_main_tag and parent_id == main_tag.id:
                    corrected_parents.append(main_tag.id)
                    has_main_tag = True
                elif not has_main_tag and parent_id in removed_set:
                    corrected_parents.append(main_tag.id)
                    has_main_tag = True
            tag.parents = corrected_parents
        commit.tags.append(main_tag)
        commit.tags.extend(tags_to_update)

        prop = (await self.get_properties(ids=[prop_id]))[0]
        value_pairs: list[tuple[int | str, Any]]
        if prop.mode == PropertyMode.id:
            values = await self._db.get_instance_property_values(property_ids=[prop_id])
            value_pairs = [(v.instance_id, v.value) for v in values]
        else:
            values = await self._db.get_image_property_values(property_ids=[prop_id])
            value_pairs = [(v.sha1, v.value) for v in values]

        to_update = []
        for pair in value_pairs:
            key, value = pair
            if not any([t in tag_set for t in value]):
                continue
            corrected_value = []
            has_main_tag = False
            for tag in value:
                if tag not in removed_set and tag != main_tag.id:
                    corrected_value.append(tag)
                elif not has_main_tag and tag == main_tag.id:
                    corrected_value.append(main_tag.id)
                    has_main_tag = True
                elif not has_main_tag and tag in removed_set:
                    corrected_value.append(main_tag.id)
                    has_main_tag = True
            pair = (key, corrected_value)
            to_update.append(pair)

        if prop.mode == PropertyMode.id:
            commit.instance_values.extend(
                [InstanceProperty(property_id=prop_id, instance_id=k, value=v) for k, v in to_update]
            )
        else:
            commit.image_values.extend(
                [ImageProperty(property_id=prop_id, sha1=k, value=v) for k, v in to_update]
            )

        commit.empty_tags.extend(tag_ids[1:])
        await self.undo_queue.do(commit)
        return commit

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

    # =========== Folders ===========
    async def add_folder(self, path: str, name: str, parent: int = None):
        return await self._db.add_folder(path, name, parent)

    async def get_folders(self):
        return await self._db.get_folders()

    async def get_folder(self, folder_id: int):
        return await self._db.get_folder(folder_id)

    async def delete_folder(self, folder_id: int):
        old_folders = {f.id for f in await self._db.get_folders()}
        old_ids = await self._db.get_all_instances_ids()
        old_sha1s = await self._db.get_all_instance_sha1s()

        await self._db.delete_folder(folder_id)

        now_folders = {f.id for f in await self._db.get_folders()}
        now_ids = await self._db.get_all_instances_ids()
        now_sha1s = await self._db.get_all_instance_sha1s()

        deleted_folders = list(old_folders - now_folders)
        deleted_ids = list(old_ids - now_ids)
        deleted_sha1s = list(old_sha1s - now_sha1s)

        await self._db.delete_images(deleted_sha1s)
        await self._db.delete_image_values(deleted_sha1s)
        await self._db.delete_vectors(deleted_sha1s)

        return DeleteFolderConfirm(deleted_folders=deleted_folders, deleted_instances=deleted_ids, deleted_sha1s=deleted_sha1s)

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

        # TODO: correct ids for property
        if commit.property_groups:
            new, old = separate_ids(commit.property_groups)
            len_new = len(new)
            if len_new:
                new_ids = await self._db.get_new_property_group_ids(len_new)
                for pg, id_ in zip(new, new_ids):
                    pg.id = id_
            await self._db.import_property_groups(commit.property_groups)

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

            tag_index = {t.id: t for t in await self.get_tags()}
            safe_update_tag_parents(tag_index, commit.tags)
            verify_tag_color(commit.tags)

            db_tags = await self._db.import_tags(commit.tags)

            tag_id_map = {old: new.id for old, new in zip(ids, db_tags)}
            for tag in commit.tags:
                tag.parents = [tId if tId not in tag_id_map else tag_id_map[tId] for tId in tag.parents]
            db_tags = await self._db.import_tags(commit.tags)

            current_ids = {tt.id for tt in current}
            inverse.empty_tags.extend([t.id for t in db_tags if t.id not in current_ids])
            inverse.tags.extend(current)

        def correct_property_id(value: InstancePropertyKey | ImagePropertyKey):
            if value.property_id in property_id_map:
                value.property_id = property_id_map[value.property_id]

        def correct_instance_id(value: InstancePropertyKey):
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
            [correct_property_id(v) for v in commit.empty_image_values]

            current = await self._db.get_image_property_values_from_keys(commit.empty_image_values)
            inverse.image_values.extend(current)
            await self._db.delete_image_property_values(commit.empty_image_values)

        if commit.empty_instance_values:
            [correct_property_id(v) for v in commit.empty_instance_values]
            [correct_instance_id(v) for v in commit.empty_instance_values]

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

        if commit.empty_property_groups:
            await self._db.delete_property_groups(commit.empty_property_groups)

        if commit.empty_instances:
            current = await self._db.get_instances(ids=commit.empty_instances)
            inverse.instances.extend(current)
            # TODO: or not to do ?
            # await self._db.delete_instance(ids=commit.empty_instances)
        return inverse

    async def stream_instance_sha1_and_url(self, chunk_size: int = 10000):
        position = 0

        while True:
            query = """
            SELECT sha1, url FROM instances
            WHERE rowid > ?
            ORDER BY rowid ASC
            LIMIT ?;
            """
            cursor = await self._db.conn.execute_query(query, (position, chunk_size))
            rows = await cursor.fetchall()

            if not rows:
                break

            for row in rows:
                yield row  # Yielding each row one at a time

            position += len(rows)
