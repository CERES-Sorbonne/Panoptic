import asyncio
import io
import os
import logging
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from PIL import Image
from panoptic.core.task.task import Task
from panoptic.models import ImageAtlas

logger = logging.getLogger('GenerateAtlasTask')

ATLAS_SIZE = 2048
CELL_SIZE = 64
CELLS_PER_ROW = ATLAS_SIZE // CELL_SIZE
CELLS_PER_SHEET = CELLS_PER_ROW ** 2


@dataclass
class ResizedCell:
    sha1: str
    data: bytes


def _resize_worker(items: list[tuple[str, bytes]]) -> list[ResizedCell]:
    """Pure CPU: resizes a batch of blobs to uniform cell size. Runs in subprocess."""
    results = []
    for sha1, blob in items:
        try:
            with Image.open(io.BytesIO(blob)) as img:
                img = img.convert('RGBA')
                img.thumbnail((CELL_SIZE, CELL_SIZE), Image.Resampling.LANCZOS)
                cell = Image.new('RGBA', (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
                x = (CELL_SIZE - img.width) // 2
                y = (CELL_SIZE - img.height) // 2
                cell.paste(img, (x, y))
                results.append(ResizedCell(sha1=sha1, data=cell.tobytes()))
        except Exception as e:
            print(f"[_resize_worker] ERROR resizing {sha1}: {e}")
    return results


class GenerateAtlasTask(Task):
    def __init__(self, project):
        super().__init__()
        self._project = project
        self.name = 'Generate Atlas'

    async def start(self):
        self.state.running = True

        instances = await self._project.db.get_instances()
        sha1s = list({i.sha1 for i in instances})
        self.state.total = len(sha1s)
        self._notify()

        print(f"[GenerateAtlasTask] Starting atlas generation for {len(sha1s)} unique sha1s")

        # Filter to sha1s that actually have a small image file on disk
        small_path = self._project.paths.image_small
        available = []
        missing = 0
        for sha1 in sha1s:
            if (small_path / f"{sha1}.jpg").exists():
                available.append(sha1)
            else:
                missing += 1

        print(f"[GenerateAtlasTask] {len(available)} small images found on disk, {missing} missing")

        if not available:
            print("[GenerateAtlasTask] No images available – aborting atlas generation")
            self.state.running = False
            self.state.finished = True
            self._finished_event.set()
            self._notify()
            return

        self._read_queue = asyncio.Queue(maxsize=10)
        self._stitch_queue = asyncio.Queue(maxsize=10)

        loop = asyncio.get_running_loop()
        with ProcessPoolExecutor(max_workers=4) as pool:
            reader_task = asyncio.create_task(self._reader_stage(available, small_path))
            compute_task = asyncio.create_task(self._compute_stage(loop, pool))
            stitcher_task = asyncio.create_task(self._stitcher_stage())

            await asyncio.gather(reader_task, compute_task, stitcher_task)

        self.state.running = False
        self.state.finished = True
        self._finished_event.set()
        self._notify()
        print("[GenerateAtlasTask] Done")

    async def _reader_stage(self, sha1s: list[str], small_path: Path):
        """Reads small image files from disk and feeds chunks to the compute stage."""
        print(f"[reader] Starting – {len(sha1s)} images to read")
        chunk = []
        read_count = 0

        for sha1 in sha1s:
            path = small_path / f"{sha1}.jpg"
            try:
                blob = await asyncio.to_thread(path.read_bytes)
                chunk.append((sha1, blob))
                read_count += 1
            except Exception as e:
                print(f"[reader] ERROR reading {sha1}: {e}")

            if len(chunk) >= 200:
                print(f"[reader] Sending chunk of {len(chunk)} – total read so far: {read_count}")
                await self._read_queue.put(chunk)
                chunk = []

        if chunk:
            print(f"[reader] Sending final chunk of {len(chunk)}")
            await self._read_queue.put(chunk)

        print(f"[reader] Done – {read_count} images read")
        await self._read_queue.put(None)

    async def _compute_stage(self, loop, pool):
        """Resizes blobs in subprocesses and feeds results to the stitcher."""
        print("[compute] Starting")
        total_cells = 0

        while True:
            chunk = await self._read_queue.get()
            if chunk is None:
                break
            cells = await loop.run_in_executor(pool, _resize_worker, chunk)
            total_cells += len(cells)
            print(f"[compute] Resized batch of {len(chunk)} → {len(cells)} cells (total: {total_cells})")
            await self._stitch_queue.put(cells)

        print(f"[compute] Done – {total_cells} cells total")
        await self._stitch_queue.put(None)

    async def _stitcher_stage(self):
        """Pastes cells into atlas sheets and saves them to disk."""
        print("[stitcher] Starting")
        sha1_mapping: dict[str, tuple[int, int]] = {}
        sheet_idx = 0
        cell_idx = 0
        current_sheet = Image.new('RGBA', (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0))

        while True:
            cells = await self._stitch_queue.get()
            if cells is None:
                break

            for cell in cells:
                if cell_idx >= CELLS_PER_SHEET:
                    print(f"[stitcher] Sheet {sheet_idx} full – saving")
                    await self._save_sheet(current_sheet, sheet_idx)
                    sheet_idx += 1
                    cell_idx = 0
                    current_sheet = Image.new('RGBA', (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0))

                row = cell_idx // CELLS_PER_ROW
                col = cell_idx % CELLS_PER_ROW
                img_cell = Image.frombytes('RGBA', (CELL_SIZE, CELL_SIZE), cell.data)
                current_sheet.paste(img_cell, (col * CELL_SIZE, row * CELL_SIZE))

                sha1_mapping[cell.sha1] = (sheet_idx, cell_idx)
                cell_idx += 1
                self.state.done += 1

            self._notify()

        # Save the last sheet even if it's not full
        if cell_idx > 0:
            print(f"[stitcher] Saving final sheet {sheet_idx} with {cell_idx} cells")
            await self._save_sheet(current_sheet, sheet_idx)
        else:
            # Edge case: last sheet was exactly full and already saved
            sheet_idx -= 1

        total_sheets = sheet_idx + 1
        print(f"[stitcher] Done – {len(sha1_mapping)} cells across {total_sheets} sheets")

        atlas = ImageAtlas(
            id=0,
            atlas_nb=total_sheets,
            width=ATLAS_SIZE,
            height=ATLAS_SIZE,
            cell_width=CELL_SIZE,
            cell_height=CELL_SIZE,
            sha1_mapping=sha1_mapping,
        )
        await self._project.db.import_atlas(atlas)
        print(f"[stitcher] Atlas metadata saved to DB")

    async def _save_sheet(self, sheet: Image.Image, index: int):
        path = self._project.paths.get_atlas_sheet_path(0, index)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print(f"[stitcher] Saving sheet {index} to {path}")
        await asyncio.to_thread(sheet.save, path, format='PNG')