import asyncio
import logging
from pathlib import Path
from typing import Callable, Coroutine

from panoptic2.core.databases.data.data_reader import DataReader


class DbWatcher:
    """Polls data.db every 100ms and calls broadcast_fn when the sequence advances.

    broadcast_fn is async: Callable[[project_id: str, sequence: int], Coroutine]
    The watcher runs entirely inside the asyncio event loop — never in a thread.
    """

    def __init__(
        self,
        data_db_path: Path,
        project_id: str,
        broadcast_fn: Callable[[str, int], Coroutine],
    ):
        self._data_db_path  = Path(data_db_path)
        self._project_id    = project_id
        self._broadcast_fn  = broadcast_fn
        self._last_seq:  int  = 0
        self._running:   bool = False

    async def run(self) -> None:
        self._running = True
        with DataReader(str(self._data_db_path)) as reader:
            self._last_seq = reader.get_next_sequence()
            while self._running:
                await asyncio.sleep(0.1)
                await self._check(reader)

    async def _check(self, reader: DataReader) -> None:
        try:
            new_seq = reader.get_next_sequence()
        except Exception:
            logging.exception("DbWatcher: error reading sequence")
            return
        if new_seq <= self._last_seq:
            return
        self._last_seq = new_seq
        try:
            await self._broadcast_fn(self._project_id, new_seq)
        except Exception:
            logging.exception("DbWatcher: error in broadcast_fn")

    def stop(self) -> None:
        """Thread-safe: set flag; run() will exit on its next iteration (≤ 100ms)."""
        self._running = False
