import asyncio
import io
import os
import time
import logging
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from PIL import Image
from panoptic.core.task.task import Task
from panoptic.models import ImageAtlas

logger = logging.getLogger('GenerateAtlasTask')

# Constants
ATLAS_SIZE = 2048
CELL_SIZE = 64
CELLS_PER_ROW = ATLAS_SIZE // CELL_SIZE
CELLS_PER_SHEET = CELLS_PER_ROW ** 2


@dataclass
class ResizedCell:
    sha1: str
    data: bytes  # Raw RGBA bytes for fast pasting


def _resize_worker(items: list[tuple[str, bytes]]) -> list[ResizedCell]:
    """Pure CPU: Resizes a batch of blobs to uniform cell size."""
    results = []
    for sha1, blob in items:
        try:
            with Image.open(io.BytesIO(blob)) as img:
                img = img.convert('RGBA')
                img.thumbnail((CELL_SIZE, CELL_SIZE), Image.Resampling.LANCZOS)
                # Create a centered 64x64 cell
                cell = Image.new('RGBA', (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
                x = (CELL_SIZE - img.width) // 2
                y = (CELL_SIZE - img.height) // 2
                cell.paste(img, (x, y))
                results.append(ResizedCell(sha1=sha1, data=cell.tobytes()))
        except Exception:
            continue
    return results


class GenerateAtlasTask(Task):
    def __init__(self, project):
        super().__init__()
        self._project = project
        self.name = 'Generate Atlas'
        self._read_queue = asyncio.Queue(maxsize=10)
        self._stitch_queue = asyncio.Queue(maxsize=10)

    async def start(self):
        self.state.running = True

        # 1. Get all SHA1s to process
        instances = await self._project.db.get_instances()
        sha1s = list({i.sha1 for i in instances})
        self.state.total = len(sha1s)
        self._notify()

        loop = asyncio.get_running_loop()
        with ProcessPoolExecutor(max_workers=4) as pool:
            # Stage 1: Reader (DB -> Queue)
            reader_task = asyncio.create_task(self._reader_stage(sha1s))
            # Stage 2: Compute (Queue -> Resize -> Queue)
            compute_task = asyncio.create_task(self._compute_stage(loop, pool))
            # Stage 3: Stitcher (Queue -> Paste -> Save)
            stitcher_task = asyncio.create_task(self._stitcher_stage())

            await asyncio.gather(reader_task, compute_task, stitcher_task)

        self.state.running = False
        self.state.finished = True
        self._finished_event.set()
        self._notify()

    async def _reader_stage(self, sha1s):
        chunk = []
        for sha1 in sha1s:
            blob = await self._project.db.get_small_image(sha1)
            if blob:
                chunk.append((sha1, blob))

            if len(chunk) >= 200:  # Small chunks to keep IPC snappy
                await self._read_queue.put(chunk)
                chunk = []

        if chunk: await self._read_queue.put(chunk)
        await self._read_queue.put(None)

    async def _compute_stage(self, loop, pool):
        while True:
            chunk = await self._read_queue.get()
            if chunk is None: break
            # Offload resizing
            cells = await loop.run_in_executor(pool, _resize_worker, chunk)
            await self._stitch_queue.put(cells)
        await self._stitch_queue.put(None)

    async def _stitcher_stage(self):
        sha1_mapping = {}
        sheet_idx = 0
        cell_idx = 0
        current_sheet = Image.new('RGBA', (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0))

        while True:
            cells = await self._stitch_queue.get()
            if cells is None: break

            for cell in cells:
                if cell_idx >= CELLS_PER_SHEET:
                    await self._save_sheet(current_sheet, sheet_idx)
                    sheet_idx += 1
                    cell_idx = 0
                    current_sheet = Image.new('RGBA', (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0))

                # Fast paste using raw bytes
                row = cell_idx // CELLS_PER_ROW
                col = cell_idx % CELLS_PER_ROW
                img_cell = Image.frombytes('RGBA', (CELL_SIZE, CELL_SIZE), cell.data)
                current_sheet.paste(img_cell, (col * CELL_SIZE, row * CELL_SIZE))

                sha1_mapping[cell.sha1] = (sheet_idx, cell_idx)
                cell_idx += 1
                self.state.done += 1

            self._notify()

        # Final cleanup
        await self._save_sheet(current_sheet, sheet_idx)

        # Save Atlas Metadata to DB
        atlas = ImageAtlas(
            id=0, atlas_nb=sheet_idx + 1,
            width=ATLAS_SIZE, height=ATLAS_SIZE,
            cell_width=CELL_SIZE, cell_height=CELL_SIZE,
            sha1_mapping=sha1_mapping
        )
        await self._project.db.import_atlas(atlas)

    async def _save_sheet(self, sheet: Image.Image, index: int):
        """Saves a single sheet to disk in a thread to keep UI alive."""
        path = self._project.paths.get_atlas_sheet_path(0, index)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Use low-quality but fast saving if speed is critical,
        # or stick to PNG for lossless atlas textures.
        await asyncio.to_thread(sheet.save, path, format='PNG')