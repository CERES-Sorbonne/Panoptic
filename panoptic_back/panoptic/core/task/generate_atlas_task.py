"""GenerateAtlasTask — reads small-image blobs from MediaDB, stitches PNG sheets.

Each sheet is independent, so each one is built in a worker process: the main
thread only reads blobs from the DB, a worker decodes them, pastes the cells and
encodes the PNG. Decoding and PNG encoding are most of the work, so this scales
with the number of cores.
"""
from __future__ import annotations

import io
import logging
import os
from concurrent.futures import Future, ProcessPoolExecutor
from pathlib import Path

from PIL import Image as PilImage

from panoptic.core.databases.media.models import ImageAtlas
from panoptic.core.task.task import Task

logger = logging.getLogger('GenerateAtlasTask')

ATLAS_SIZE     = 2048
CELL_SIZE      = 64
CELLS_PER_ROW  = ATLAS_SIZE // CELL_SIZE   # 32
CELLS_PER_SHEET = CELLS_PER_ROW ** 2       # 1024
BATCH_SIZE     = 200
ATLAS_ID       = 0


class GenerateAtlasTask(Task):
    def __init__(self, project):
        super().__init__()
        self.name     = 'Generate Atlas'
        self._project = project
        self.max_workers = min(os.cpu_count() or 4, 10)

    def start(self):
        instances = self._project.get_instances()
        sha1s     = list({i.sha1 for i in instances})
        self.state.total = len(sha1s)
        self._notify()

        if not sha1s:
            logger.info('No instances — skipping atlas generation')
            return

        atlas_dir = self._project.folder / 'atlas'
        atlas_dir.mkdir(parents=True, exist_ok=True)

        sheets = [sha1s[i:i + CELLS_PER_SHEET] for i in range(0, len(sha1s), CELLS_PER_SHEET)]
        sha1_mapping: dict[str, tuple[int, int]] = {}

        def collect(sheet_idx: int, placed: list[str], size: int):
            for cell_idx, sha1 in enumerate(placed):
                sha1_mapping[sha1] = (sheet_idx, cell_idx)
            self.state.done += size
            self._notify()

        if len(sheets) == 1:
            # one sheet gains nothing from a pool, and starting one costs more than the work
            collect(0, _build_sheet(self._read_blobs(sheets[0]), atlas_dir, 0), len(sheets[0]))
        else:
            workers = min(self.max_workers, len(sheets))
            self.set_workers(workers)
            # Each pending sheet holds its blobs in memory: keep only a few ahead of the workers.
            max_pending = workers * 2
            pending: list[tuple[int, Future, int]] = []
            with ProcessPoolExecutor(max_workers=workers) as pool:
                for sheet_idx, sheet in enumerate(sheets):
                    if self._cancel_event.is_set():
                        pool.shutdown(wait=False, cancel_futures=True)
                        return
                    if len(pending) >= max_pending:
                        idx, future, size = pending.pop(0)
                        collect(idx, future.result(), size)
                    future = pool.submit(_build_sheet, self._read_blobs(sheet), atlas_dir, sheet_idx)
                    pending.append((sheet_idx, future, len(sheet)))
                for idx, future, size in pending:
                    collect(idx, future.result(), size)

        if not sha1_mapping:
            logger.warning('No small images available — atlas not created')
            return

        atlas = ImageAtlas(
            id=ATLAS_ID,
            atlas_nb=len(sheets),
            width=ATLAS_SIZE,
            height=ATLAS_SIZE,
            cell_width=CELL_SIZE,
            cell_height=CELL_SIZE,
            sha1_mapping=sha1_mapping,
        )
        self._project.upsert_image_atlas(atlas)
        logger.info('Atlas saved: %d cells across %d sheets', len(sha1_mapping), len(sheets))

    def _read_blobs(self, sha1s: list[str]) -> list[tuple[str, bytes]]:
        """The small-image blob of each sha1 that has one, in the given order."""
        blobs: dict[str, bytes] = {}
        for start in range(0, len(sha1s), BATCH_SIZE):
            batch = sha1s[start:start + BATCH_SIZE]
            blobs.update((img.sha1, img.data) for img in self._project.get_images(type_id=1, sha1=batch))
        return [(sha1, blobs[sha1]) for sha1 in sha1s if sha1 in blobs]


def _build_sheet(blobs: list[tuple[str, bytes]], atlas_dir: Path, index: int) -> list[str]:
    """Paste every blob into one sheet and save it. Runs in a worker process.

    Returns the sha1s placed, in cell order. Blobs that fail to decode are skipped.
    """
    sheet = PilImage.new('RGBA', (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0))
    placed: list[str] = []
    for sha1, blob in blobs:
        cell = _resize_cell(blob, sha1)
        if cell is None:
            continue
        cell_idx = len(placed)
        x = (cell_idx % CELLS_PER_ROW) * CELL_SIZE + (CELL_SIZE - cell.width) // 2
        y = (cell_idx // CELLS_PER_ROW) * CELL_SIZE + (CELL_SIZE - cell.height) // 2
        sheet.paste(cell, (x, y))
        placed.append(sha1)
    _save_sheet(sheet, atlas_dir, index)
    return placed


def _resize_cell(blob: bytes, sha1: str) -> PilImage.Image | None:
    try:
        with PilImage.open(io.BytesIO(blob)) as img:
            # JPEG only: decode straight at a reduced scale instead of full size
            img.draft('RGB', (CELL_SIZE * 2, CELL_SIZE * 2))
            # resizing RGB is much cheaper than RGBA, so only keep alpha when there is some
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA' if img.has_transparency_data else 'RGB')
            img.thumbnail((CELL_SIZE, CELL_SIZE), PilImage.Resampling.LANCZOS)
            img.load()
            return img
    except Exception as e:
        logger.error('Failed to resize %s: %s', sha1, e)
        return None


def _save_sheet(sheet: PilImage.Image, atlas_dir: Path, index: int) -> None:
    path = atlas_dir / f'{ATLAS_ID}_{index}.png'
    sheet.save(path, format='PNG')
    logger.info('Saved atlas sheet %d → %s', index, path)
