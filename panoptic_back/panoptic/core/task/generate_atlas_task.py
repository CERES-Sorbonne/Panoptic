"""GenerateAtlasTask — reads small-image blobs from MediaDB, stitches PNG sheets."""
from __future__ import annotations

import io
import logging
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

    def start(self):
        instances = self._project.get_instances()
        sha1s     = list({i.sha1 for i in instances})
        self.state.total = len(sha1s)
        self._notify()

        if not sha1s:
            logger.info('No instances — skipping atlas generation')
            return

        sha1_mapping: dict[str, tuple[int, int]] = {}
        sheet_idx    = 0
        cell_idx     = 0
        current_sheet = PilImage.new('RGBA', (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0))

        atlas_dir = self._project.folder / 'atlas'
        atlas_dir.mkdir(parents=True, exist_ok=True)

        for batch_start in range(0, len(sha1s), BATCH_SIZE):
            if self._cancel_event.is_set():
                return

            batch  = sha1s[batch_start:batch_start + BATCH_SIZE]
            images = self._project.get_images(type_id=1, sha1=batch)
            blobs  = {img.sha1: img.data for img in images}

            for sha1 in batch:
                blob = blobs.get(sha1)
                if blob is None:
                    self.state.done += 1
                    continue

                if cell_idx >= CELLS_PER_SHEET:
                    _save_sheet(current_sheet, atlas_dir, sheet_idx)
                    sheet_idx    += 1
                    cell_idx      = 0
                    current_sheet = PilImage.new('RGBA', (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0))

                cell = _resize_cell(blob, sha1)
                if cell is not None:
                    row = cell_idx // CELLS_PER_ROW
                    col = cell_idx % CELLS_PER_ROW
                    current_sheet.paste(cell, (col * CELL_SIZE, row * CELL_SIZE))
                    sha1_mapping[sha1] = (sheet_idx, cell_idx)
                    cell_idx += 1

                self.state.done += 1
                self._notify()

        if not sha1_mapping:
            logger.warning('No small images available — atlas not created')
            return

        if cell_idx > 0:
            _save_sheet(current_sheet, atlas_dir, sheet_idx)
            total_sheets = sheet_idx + 1
        else:
            # Last sheet was exactly full and already saved before sheet_idx was incremented
            total_sheets = sheet_idx

        atlas = ImageAtlas(
            id=ATLAS_ID,
            atlas_nb=total_sheets,
            width=ATLAS_SIZE,
            height=ATLAS_SIZE,
            cell_width=CELL_SIZE,
            cell_height=CELL_SIZE,
            sha1_mapping=sha1_mapping,
        )
        self._project.upsert_image_atlas(atlas)
        logger.info('Atlas saved: %d cells across %d sheets', len(sha1_mapping), total_sheets)


def _resize_cell(blob: bytes, sha1: str) -> PilImage.Image | None:
    try:
        with PilImage.open(io.BytesIO(blob)) as img:
            img = img.convert('RGBA')
            img.thumbnail((CELL_SIZE, CELL_SIZE), PilImage.Resampling.LANCZOS)
            cell = PilImage.new('RGBA', (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
            x = (CELL_SIZE - img.width) // 2
            y = (CELL_SIZE - img.height) // 2
            cell.paste(img, (x, y))
            return cell
    except Exception as e:
        logger.error('Failed to resize %s: %s', sha1, e)
        return None


def _save_sheet(sheet: PilImage.Image, atlas_dir: Path, index: int) -> None:
    path = atlas_dir / f'{ATLAS_ID}_{index}.png'
    sheet.save(path, format='PNG')
    logger.info('Saved atlas sheet %d → %s', index, path)
