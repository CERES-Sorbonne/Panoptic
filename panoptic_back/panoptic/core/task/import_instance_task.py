import asyncio
import hashlib
import io
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from PIL import Image
from imagehash import average_hash

from panoptic.core.task.task import Task
from panoptic.models import DbCommit, Instance

logger = logging.getLogger('InstanceTask')


@dataclass
class RawImageItem:
    file_path: str
    folder_id: int
    raw_bytes: bytes


@dataclass
class ProcessedImageItem:
    file_path: str
    folder_id: int
    name: str
    extension: str
    sha1: str
    width: int
    height: int
    ahash: str
    mime_type: str
    large_bytes: bytes | None
    small_bytes: bytes | None


# --- WORKER: CPU INTENSIVE ---
def _compute_worker(items: list[RawImageItem], settings) -> list[ProcessedImageItem]:
    results = []
    target_max = max(settings.image_large_size, settings.image_small_size)

    for item in items:
        try:
            name = os.path.basename(item.file_path)
            ext = os.path.splitext(name)[1].lower()
            sha1 = hashlib.sha1(item.raw_bytes).hexdigest()

            with Image.open(io.BytesIO(item.raw_bytes)) as image:
                if image.format == 'JPEG':
                    image.draft('RGB', (target_max, target_max))

                image.load()
                width, height = image.size
                if image.mode != 'RGB':
                    image = image.convert('RGB')

                def get_bytes(img, size):
                    if img.width > size or img.height > size:
                        img.thumbnail((size, size))
                    buf = io.BytesIO()
                    img.save(buf, format='jpeg', quality=30)
                    return buf.getvalue()

                large_bytes = get_bytes(image.copy(), settings.image_large_size) if settings.save_image_large else None

                # Resize for small thumbnail and hashing
                if image.width > settings.image_small_size or image.height > settings.image_small_size:
                    image.thumbnail((settings.image_small_size, settings.image_small_size))

                small_bytes = get_bytes(image, settings.image_small_size) if settings.save_image_small else None
                ahash = str(average_hash(image))

                results.append(ProcessedImageItem(
                    file_path=item.file_path, folder_id=item.folder_id, name=name, extension=ext,
                    sha1=sha1, width=width, height=height, ahash=ahash,
                    mime_type='image/jpeg', large_bytes=large_bytes, small_bytes=small_bytes
                ))
        except Exception as e:
            logger.error(f"Worker failed on {item.file_path}: {e}")
    return results


# --- MAIN TASK ---
class ImportInstanceTask(Task):
    def __init__(self, project, files: list[tuple[str, int]]):
        super().__init__()
        self._project = project
        self._files = files
        self.state.total = len(files)

        # Buffering: 30 images per chunk is the "Goldilocks" zone for IPC
        self.chunk_size = 30
        self._read_queue = asyncio.Queue(maxsize=10)
        self._write_queue = asyncio.Queue(maxsize=10)

    async def start(self):
        self.state.running = True
        self._notify()
        start_time = time.perf_counter()

        # 10 workers leaves room for the main loop and SSD controller overhead
        with ProcessPoolExecutor(max_workers=10) as pool:
            await asyncio.gather(
                self._reader_stage(),
                self._compute_stage(pool),
                self._writer_stage()
            )

        duration = time.perf_counter() - start_time
        img_per_sec = self.state.total / duration if duration > 0 else 0

        self.state.running = False
        self.state.finished = True
        self.state.done = self.state.total
        self._notify()

        print(f"\nImage Import: {img_per_sec:.1f} images/sec")
        logger.info(f"Imported {self.state.total} images in {duration:.2f}s")

    async def _reader_stage(self):
        """Sequential Read: Thread-offloaded to avoid blocking the event loop."""
        chunk = []
        for file_path, folder_id in self._files:
            if self._cancel_event.is_set(): break

            # Sequential reads are best for SSD long-term health and consistent latency
            raw_bytes = await asyncio.to_thread(self._read_file, file_path)
            if raw_bytes:
                chunk.append(RawImageItem(file_path, folder_id, raw_bytes))

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
        loop = asyncio.get_running_loop()
        settings = self._project.settings
        pending = set()

        while True:
            chunk = await self._read_queue.get()
            if chunk is None: break

            task = loop.run_in_executor(pool, _compute_worker, chunk, settings)
            pending.add(task)

            # Limit active tasks to prevent memory spikes
            if len(pending) >= 15:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for d in done:
                    await self._write_queue.put(await d)

        if pending:
            results = await asyncio.gather(*pending)
            for r in results: await self._write_queue.put(r)

        await self._write_queue.put(None)

    async def _writer_stage(self):
        paths, db = self._project.paths, self._project.db
        accumulated = []
        batch_limit = 120  # Balanced DB transaction size

        def _io_block(chunk):
            """Writes chunk to disk in a single thread pass."""
            batch = []
            for item in chunk:
                fn = f"{item.sha1}.jpg"
                try:
                    for data, root in [(item.small_bytes, paths.image_small), (item.large_bytes, paths.image_large)]:
                        if data:
                            with open(os.path.join(root, fn), 'wb') as f: f.write(data)

                    batch.append(Instance(
                        id=-1, folder_id=item.folder_id, name=item.name, extension=item.extension,
                        sha1=item.sha1, url=item.file_path, height=item.height, width=item.width, ahash=item.ahash
                    ))
                except:
                    continue
            return batch

        while True:
            chunk = await self._write_queue.get()
            if chunk is not None:
                new_inst = await asyncio.to_thread(_io_block, chunk)
                accumulated.extend(new_inst)
                self.state.done += len(chunk)
                self._notify()

            if len(accumulated) >= batch_limit or (chunk is None and accumulated):
                await db.apply_commit(DbCommit(instances=accumulated))
                for inst in accumulated:
                    self._project.sha1_to_files[inst.sha1].append(inst.url)
                accumulated = []

            if chunk is None: break