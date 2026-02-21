import asyncio
import io
import os
import time
import logging
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from PIL import Image
from panoptic.core.task.task import Task

logger = logging.getLogger('ImportImageTask')


@dataclass
class ImageMiniatureResult:
    sha1: str
    small: bytes | None
    medium: bytes | None
    large: bytes | None
    raw: bytes | None


# --- PURE COMPUTE WORKER ---
def _import_image_worker(items: list[tuple[str, bytes]], settings) -> list[ImageMiniatureResult]:
    results = []
    # Optimization: Pre-calculate max size for JPEG draft
    sizes = [s for s in [settings.image_large_size, settings.image_medium_size, settings.image_small_size]]
    target_max = max(sizes) if sizes else 1024

    for sha1, raw_input_bytes in items:
        try:
            with Image.open(io.BytesIO(raw_input_bytes)) as image:
                # JPEG Draft loading for speed
                if image.format == 'JPEG':
                    image.draft('RGB', (target_max, target_max))

                image.load()
                if image.mode != 'RGB':
                    image = image.convert('RGB')

                def get_thumb_bytes(img, size):
                    if img.width > size or img.height > size:
                        img.thumbnail((size, size))
                    buf = io.BytesIO()
                    img.save(buf, format='jpeg', quality=30)
                    return buf.getvalue()

                # Process thumbnails in descending order
                large = get_thumb_bytes(image.copy(), settings.image_large_size) if settings.save_image_large else None
                medium = get_thumb_bytes(image.copy(),
                                         settings.image_medium_size) if settings.save_image_medium else None

                # Small/Last reuse the final state of 'image'
                small = get_thumb_bytes(image, settings.image_small_size) if settings.save_image_small else None

                results.append(ImageMiniatureResult(
                    sha1=sha1, small=small, medium=medium, large=large,
                    raw=raw_input_bytes if settings.save_file_raw else None
                ))
        except Exception as e:
            logger.error(f"Worker failed on {sha1}: {e}")
    return results


# --- TASK PIPELINE ---
class ImportImageTask(Task):
    def __init__(self, sha1s: list[str], project):
        super().__init__()
        self.name = 'Import Image Miniature'
        self._project = project
        self._sha1s = sha1s
        self.state.total = len(sha1s)

        self.chunk_size = 30
        self._read_queue = asyncio.Queue(maxsize=10)
        self._write_queue = asyncio.Queue(maxsize=10)

    async def start(self):
        self.state.running = True
        self._notify()
        start_time = time.perf_counter()

        # Using 10 workers for M4 Pro to leave breathing room for I/O stages
        with ProcessPoolExecutor(max_workers=10) as pool:
            await asyncio.gather(
                self._reader_stage(),
                self._compute_stage(pool),
                self._writer_stage()
            )

        self.state.running = False
        self.state.finished = True
        self._notify()

        duration = time.perf_counter() - start_time
        logger.info(f"Miniature import complete: {self.state.total} images at {self.state.total / duration:.1f} img/s")

    async def _reader_stage(self):
        """Stage 1: Read raw files from disk into memory."""
        chunk = []
        for sha1 in self._sha1s:
            if self._cancel_event.is_set(): break

            files = self._project.sha1_to_files.get(sha1)
            if not files: continue

            # Offload blocking disk read to thread
            raw_bytes = await asyncio.to_thread(self._read_file, files[0])
            if raw_bytes:
                chunk.append((sha1, raw_bytes))

            if len(chunk) >= self.chunk_size:
                await self._read_queue.put(chunk)
                chunk = []

        if chunk: await self._read_queue.put(chunk)
        await self._read_queue.put(None)

    def _read_file(self, path):
        try:
            with open(path, 'rb') as f:
                return f.read()
        except:
            return None

    async def _compute_stage(self, pool):
        """Stage 2: Multiprocessing compute."""
        loop = asyncio.get_running_loop()
        settings = self._project.settings
        pending = set()

        while True:
            chunk = await self._read_queue.get()
            if chunk is None: break

            task = loop.run_in_executor(pool, _import_image_worker, chunk, settings)
            pending.add(task)

            if len(pending) >= 15:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for d in done:
                    await self._write_queue.put(await d)

        if pending:
            results = await asyncio.gather(*pending)
            for r in results: await self._write_queue.put(r)

        await self._write_queue.put(None)

    async def _writer_stage(self):
        """Stage 3: Batched Database Writes."""
        db = self._project.db
        accumulated = []
        batch_limit = 100

        while True:
            chunk = await self._write_queue.get()

            if chunk is not None:
                accumulated.extend(chunk)
                self.state.done += len(chunk)
                self._notify()

            if len(accumulated) >= batch_limit or (chunk is None and accumulated):
                # Using the batch import method we discussed to avoid lock contention
                # This assumes your DB wrapper has a method to handle a list of results
                await db.import_miniatures_batch(accumulated)
                accumulated = []

            if chunk is None:
                break