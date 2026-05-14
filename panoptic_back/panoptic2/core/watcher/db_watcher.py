import asyncio
import logging
from pathlib import Path
from typing import Callable, Coroutine

from panoptic.core.databases.data.data_reader import DataReader


class DbWatcher:
    """Polls data.db every 100ms and calls broadcast_fn with new commit IDs.

    broadcast_fn is async: Callable[[project_uid: str, commit_ids: list[int]], Coroutine]
    The watcher runs entirely inside the asyncio event loop — never in a thread.
    """

    def __init__(
        self,
        data_db_path: Path,
        project_uid: str,
        broadcast_fn: Callable[[str, list[int]], Coroutine],
    ):
        self._data_db_path  = Path(data_db_path)
        self._project_uid   = project_uid
        self._broadcast_fn  = broadcast_fn
        self._last_seq:  int  = 0
        self._running:   bool = False

    async def run(self) -> None:
        self._running = True
        with DataReader(str(self._data_db_path)) as reader:
            self._last_seq = reader.get_max_commit_id()
            while self._running:
                await asyncio.sleep(0.1)
                await self._check(reader)

    async def _check(self, reader: DataReader) -> None:
        try:
            commits = reader.get_commits_since(self._last_seq)
        except Exception:
            logging.exception("DbWatcher: error reading commits")
            return
        if not commits:
            return
        self._last_seq = max(c.id for c in commits)
        commit_ids = [c.id for c in commits]
        try:
            await self._broadcast_fn(self._project_uid, commit_ids)
        except Exception:
            logging.exception("DbWatcher: error in broadcast_fn")

    def stop(self) -> None:
        """Thread-safe: set flag; run() will exit on its next iteration (≤ 100ms)."""
        self._running = False
