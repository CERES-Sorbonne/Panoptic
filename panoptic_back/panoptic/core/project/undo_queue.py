from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from panoptic.core.project.project_db import ProjectDb

from panoptic.models import DbCommit, CommitStat, CommitHistory


class UndoQueue:
    def __init__(self, db: ProjectDb):
        self._to_undo: list[DbCommit] = []
        self._to_redo: list[DbCommit] = []
        self._db = db

    async def do(self, commit: DbCommit):
        self._to_redo.clear()
        inverse = await self._db.apply_commit(commit)
        self._to_undo.append(inverse)
        undo, redo = self.stats()
        commit.history = CommitHistory(undo=undo, redo=redo)
        return commit

    async def undo(self):
        if not self._to_undo:
            return DbCommit()
        last = self._to_undo.pop()
        inverse = await self._db.apply_commit(last)
        self._to_redo.append(inverse)
        undo, redo = self.stats()
        last.history = CommitHistory(undo=undo, redo=redo)
        return last

    async def redo(self):
        if not self._to_redo:
            return DbCommit()
        last = self._to_redo.pop()
        inverse = await self._db.apply_commit(last)
        self._to_undo.append(inverse)
        undo, redo = self.stats()
        last.history = CommitHistory(undo=undo, redo=redo)
        return last

    def stats(self):
        def to_stats(c: DbCommit):
            tag_count = len(c.tags) + len(c.empty_tags)
            value_count = len(c.empty_instance_values) + len(c.instance_values)
            value_count += len(c.empty_image_values) + len(c.image_values)
            return CommitStat(timestamp=c.timestamp, tags=tag_count, values=value_count)

        undo = [to_stats(c) for c in self._to_undo]
        redo = [to_stats(c) for c in self._to_redo]
        return undo, redo
