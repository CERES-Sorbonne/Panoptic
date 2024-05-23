from panoptic.core.project.project_db import ProjectDb
from panoptic.models import DbCommit, CommitStat, InstancePropertyValue, ImagePropertyValue
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
        inverse = await self.apply_commit(last)
        self._to_redo.append(inverse)
        return last

    async def redo(self):
        if not self._to_redo:
            return DbCommit()
        last = self._to_redo.pop()
        inverse = await self.apply_commit(last)
        self._to_undo.append(inverse)
        return last

    async def do(self, commit: DbCommit):
        self._to_redo.clear()
        inverse = await self.apply_commit(commit)
        self._to_undo.append(inverse)
        return commit

    def stats(self):
        def to_stats(c: DbCommit):
            tag_count = len(c.tags) + len(c.empty_tags)
            value_count = len(c.empty_instance_values) + len(c.instance_values)
            value_count += len(c.empty_image_values) + len(c.empty_image_values)
            return CommitStat(timestamp=c.timestamp, tags=tag_count, values=value_count)
        undo = [to_stats(c) for c in self._to_undo]
        redo = [to_stats(c) for c in self._to_redo]
        return undo, redo

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
            for v in commit.instance_values:
                v.value = clean_value(properties[v.property_id], v.value)
                if v.value is None:
                    commit.empty_instance_values.append(v)
            commit.instance_values = [v for v in commit.instance_values if v.value is not None]

        if commit.image_values:
            for v in commit.image_values:
                v.value = clean_value(properties[v.property_id], v.value)
                if v.value is None:
                    commit.empty_image_values.append(v)
            commit.image_values = [v for v in commit.image_values if v.value is not None]

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
            current = await self._db.get_properties()
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
            db_instances = await self._raw_db.import_instances(commit.instances)
            instance_id_map = {old: new.id for old, new in zip(ids, db_instances)}

            current_ids = {i.id for i in current}
            inverse.empty_instances.extend([i.id for i in db_instances if i.id not in current_ids])
            inverse.instances.extend(current)

        if commit.properties:
            ids = [p.id for p in commit.properties]
            current = await self._raw_db.get_properties(ids=ids)
            db_properties = await self._raw_db.import_properties(commit.properties)
            property_id_map = {old: new.id for old, new in zip(ids, db_properties)}
            print(property_id_map)

            current_ids = {p.id for p in current}
            inverse.empty_properties.extend([p.id for p in db_properties if p.id not in current_ids])
            inverse.properties.extend(current)

        if commit.tags:
            ids = [t.id for t in commit.tags]
            current = await self._db.get_tags_by_ids(ids=ids)
            for tag in commit.tags:
                if tag.property_id in property_id_map:
                    tag.property_id = property_id_map[tag.property_id]
            db_tags = await self._raw_db.import_tags(commit.tags)
            print(ids, db_tags)
            tag_id_map = {old: new.id for old, new in zip(ids, db_tags)}

            current_ids = {tt.id for tt in current}
            inverse.empty_tags.extend([t.id for t in db_tags if t.id not in current_ids])
            inverse.tags.extend(current)

        def correct_property_id(value: InstancePropertyValue | ImagePropertyValue):
            if value.property_id in property_id_map:
                value.property_id = property_id_map[value.property_id]

        def correct_instance_id(value: InstancePropertyValue):
            if value.instance_id in instance_id_map:
                value.instance_id = instance_id_map[value.instance_id]

        def correct_tag_id(value: InstancePropertyValue | ImagePropertyValue):
            if isinstance(value.value, list):
                value.value = [tId if tId not in tag_id_map else tag_id_map[tId] for tId in value.value]

        if commit.instance_values:
            [correct_property_id(v) for v in commit.instance_values]
            [correct_instance_id(v) for v in commit.instance_values]
            [correct_tag_id(v) for v in commit.instance_values]

            current = await self._raw_db.get_instance_property_values_from_keys(commit.instance_values)
            existing = {}
            for v in current:
                if v.property_id not in existing:
                    existing[v.property_id] = {}
                existing[v.property_id][v.instance_id] = True
            print(commit.instance_values)
            await self._raw_db.import_instance_property_values(commit.instance_values)

            missing_ids = [v for v in commit.instance_values
                           if v.property_id not in existing or v.instance_id not in existing[v.property_id]]
            inverse.empty_instance_values.extend(missing_ids)
            inverse.instance_values.extend(current)

        if commit.image_values:
            [correct_property_id(v) for v in commit.instance_values]
            [correct_tag_id(v) for v in commit.instance_values]

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
