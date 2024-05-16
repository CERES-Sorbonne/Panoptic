from panoptic.core.project.project_db import ProjectDb
from panoptic.models import DbCommit
from panoptic.utils import clean_value


class UndoQueue:
    def __init__(self, db: ProjectDb):
        self._to_undo: list[DbCommit] = []
        self._to_redo: list[DbCommit] = []
        self._db = db
        self._raw_db = db.get_raw_db()

    def add_commit(self, commit: DbCommit):
        self._to_undo.append(commit)
        self._to_redo.clear()

    async def undo(self):
        if not self._to_undo:
            return DbCommit()
        last = self._to_undo.pop()
        inverse = await self._apply_commit(last)
        print('undo')
        print(inverse)
        self._to_redo.append(inverse)
        return last

    async def redo(self):
        if not self._to_redo:
            return DbCommit()
        last = self._to_redo.pop()
        inverse = await self._apply_commit(last)
        print('redo')
        print(inverse)
        self._to_undo.append(inverse)
        return last

    async def do(self, commit: DbCommit):
        self._to_redo.clear()
        inverse = await self._apply_commit(commit)
        print('do')
        print(inverse)
        self._to_undo.append(inverse)
        return commit

    async def _apply_commit(self, commit: DbCommit):
        inverse = DbCommit()
        properties = {p.id: p for p in await self._db.get_properties(no_computed=True)}

        if commit.instance_values:
            for v in commit.instance_values:
                v.value = clean_value(properties[v.property_id], v.value)
                if v.value is None:
                    commit.empty_instance_values.append(v)
            commit.instance_values.extend([v for v in commit.instance_values if v.value is not None])

        if commit.image_values:
            for v in commit.image_values:
                v.value = clean_value(properties[v.property_id], v.value)
                if v.value is None:
                    commit.empty_image_values.append(v)
            commit.image_values.extend([v for v in commit.image_values if v.value is not None])

        if commit.empty_image_values:
            current = await self._raw_db.get_image_property_values_from_keys(commit.empty_image_values)
            inverse.image_values.extend(current)
            await self._raw_db.delete_image_property_values(commit.empty_image_values)

        if commit.empty_instance_values:
            current = await self._raw_db.get_instance_property_values_from_keys(commit.empty_instance_values)
            inverse.instance_values.extend(current)
            await self._raw_db.delete_instance_property_values(commit.empty_instance_values)

        if commit.empty_tags:
            current = await self._db.get_tags_by_ids(commit.empty_tags)
            inverse.tags.extend(current)
            [await self._db.delete_tag(tid) for tid in commit.empty_tags]

        if commit.empty_properties:
            current = await self._db.get_properties(no_computed=True)
            inverse.properties.extend([p for p in current if p.id in commit.empty_properties])
            [await self._db.delete_property(pid) for pid in commit.empty_properties]

        if commit.empty_instances:
            current = await self._db.get_instances(ids=commit.empty_instances)
            inverse.instances.extend(current)
            # TODO: or not to do ?
            # await self._db.delete_instance(ids=commit.empty_instances)

        if commit.instances:
            ids = [i.id for i in commit.instances]
            current = await self._db.get_instances(ids=ids)
            for i in commit.instances:
                await self._raw_db.import_instance(i.id, i.folder_id, i.name, i.extension, i.sha1, i.url, i.width,
                                                   i.height, i.ahash)
            inverse.empty_instances.extend([i for i in ids if i not in {ii.id for ii in current}])
            inverse.instances.extend(current)

        if commit.properties:
            ids = [p.id for p in commit.properties]
            current = [p for p in await self._db.get_properties(no_computed=True) if p.id in ids]
            for p in commit.properties:
                await self._raw_db.import_property(p.id, p.name, p.type.value, p.mode.value)

            inverse.empty_properties.extend([i for i in ids if i not in {p.id for p in current}])
            inverse.properties.extend(current)

        if commit.tags:
            ids = [t.id for t in commit.tags]
            current = await self._db.get_tags_by_ids(ids=ids)
            await self._raw_db.import_tags(commit.tags)

            inverse.empty_tags.extend([t.id for t in commit.tags if t.id not in {tt.id for tt in current}])
            inverse.tags.extend(current)

        if commit.instance_values:
            current = await self._raw_db.get_instance_property_values_from_keys(commit.instance_values)
            existing = {}
            for v in current:
                if v.property_id not in existing:
                    existing[v.property_id] = {}
                existing[v.property_id][v.instance_id] = True
            await self._raw_db.import_instance_property_values(commit.instance_values)

            missing_ids = [v for v in commit.instance_values
                           if v.property_id not in existing or v.instance_id not in existing[v.property_id]]
            inverse.empty_instance_values.extend(missing_ids)
            inverse.instance_values.extend(current)

        if commit.image_values:
            current = await self._raw_db.get_image_property_values_from_keys(commit.image_values)
            existing = {}
            for v in current:
                if v.property_id not in existing:
                    existing[v.property_id] = {}
                existing[v.property_id][v.sha1] = True
            await self._raw_db.import_image_property_values(commit.image_values)

            missing_ids = [v for v in commit.image_values
                           if v.property_id not in existing or v.sha1 not in existing[v.property_id]]
            inverse.empty_image_values.extend(missing_ids)
            inverse.image_values.extend(current)

        return inverse
