from panoptic.core.project.project_db import ProjectDb
from panoptic.models import DbCommit


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
            return
        last = self._to_undo.pop()
        await self._undo_commit(last, from_redo=False)

    async def redo(self):
        if not self._to_redo:
            return
        last = self._to_redo.pop()
        await self._undo_commit(last, from_redo=True)

    async def _undo_commit(self, commit: DbCommit, from_redo=False):
        inverse = DbCommit()

        if commit.created_image_values:
            prop_ids, sha1s = zip(*[(key.property_id, key.sha1) for key in commit.created_image_values])
            current = await self._raw_db.get_image_property_values(property_ids=prop_ids, sha1s=sha1s)
            inverse.old_image_values = current
            await self._raw_db.delete_image_property_value(property_id=prop_ids, sha1s=sha1s)

        if commit.created_instance_values:
            prop_ids, inst_ids = zip(*[(key.property_id, key.instance_id) for key in commit.created_instance_values])
            current = await self._raw_db.get_instance_property_values(property_ids=prop_ids, instance_ids=inst_ids)
            inverse.old_instance_values = current
            await self._raw_db.delete_instance_property_value(property_id=prop_ids, instance_ids=inst_ids)

        if commit.created_tags:
            current = await self._db.get_tags_by_ids(commit.created_tags)
            inverse.old_tags = current
            [await self._db.delete_tag(tid) for tid in commit.created_tags]

        if commit.created_properties:
            current = await self._db.get_properties(no_computed=True)
            inverse.old_properties = [p for p in current if p.id in commit.created_properties]
            [await self._db.delete_property(pid) for pid in commit.created_properties]

        if commit.created_instances:
            current = await self._db.get_instances(ids=commit.created_instances)
            inverse.old_instances = current
            # TODO: or not to do ?
            # await self._db.delete_instance(ids=commit.created_instances)

        if commit.old_instances:
            ids = [i.id for i in commit.old_instances]
            current = await self._db.get_instances(ids=ids)
            for i in commit.old_instances:
                await self._raw_db.import_instance(i.id, i.folder_id, i.name, i.extension, i.sha1, i.url, i.width,
                                                   i.height, i.ahash)
            inverse.created_instances = [i for i in ids if i not in {ii.id for ii in current}]
            inverse.old_instances = current

        if commit.old_properties:
            ids = [p.id for p in commit.old_properties]
            current = [p for p in await self._db.get_properties(no_computed=True) if p.id in ids]
            for p in commit.old_properties:
                await self._raw_db.import_property(p.id, p.name, p.type.value, p.mode.value)

            inverse.created_properties = [i for i in ids if i not in {p.id for p in current}]
            inverse.old_properties = current

        if commit.old_tags:
            ids = [t.id for t in commit.old_tags]
            current = await self._db.get_tags_by_ids(ids=ids)
            await self._raw_db.import_tags(commit.old_tags)

            inverse.created_tags = [t.id for t in commit.old_tags if t.id not in {tt.id for tt in current}]
            inverse.old_tags = current

        if commit.old_instance_values:
            current = await self._raw_db.get_instance_property_values_from_keys(commit.old_instance_values)
            existing = {}
            for v in current:
                if not existing[v.property_id]:
                    existing[v.property_id] = {}
                existing[v.property_id][v.instance_id] = True
            await self._raw_db.import_instance_property_values(commit.old_instance_values)

            missing_ids = [v for v in commit.old_instance_values
                           if v.property_id not in existing or v.instance_id not in existing[v.property_id]]
            inverse.created_instance_values = missing_ids
            inverse.old_instance_values = current

        if commit.old_image_values:
            current = await self._raw_db.get_image_property_values_from_keys(commit.old_image_values)
            existing = {}
            for v in current:
                if not existing[v.property_id]:
                    existing[v.property_id] = {}
                existing[v.property_id][v.sha1] = True
            await self._raw_db.import_image_property_values(commit.old_image_values)

            missing_ids = [v for v in commit.old_image_values
                           if v.property_id not in existing or v.sha1 not in existing[v.property_id]]
            inverse.created_image_values = missing_ids
            inverse.old_image_values = current

        if from_redo:
            self._to_undo.append(inverse)
        else:
            self._to_redo.append(inverse)
