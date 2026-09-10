"""GenerateThumbnailsTask — backfills missing thumbnails from the original files.

Thumbnails are normally produced once, at import time. A project can still end
up with sha1s that have no stored blob: a converted legacy project whose old
format kept thumbnails on disk (or kept none at all), or an image type added
after the images were imported.

This task closes that gap *without* re-importing: it walks the instances already
in the DB, resolves each sha1 back to its local file, and renders only the
renditions that are missing, through the same `render` code the importer uses.
No new instances, no re-hashing, no duplicates. Remote (IIIF) sha1s have no
local file and are skipped.

Rendering runs in the same kind of process pool the importer uses
(LocalFileSourceReader), and every path is resolved in one bulk query rather
than one DB connection per sha1 — otherwise a backfill is an order of magnitude
slower than the import that produced the same images.

It is queued automatically at project start when the `thumbnails_dirty` project
flag is set, and clears the flag when it completes without being cancelled.
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ProcessPoolExecutor

from panoptic.core.databases.media.models import Image
from panoptic.core.databases.project.project_db import ProjectDB
from panoptic.core.file_source.processing import ImageTypeSpec, render
from panoptic.core.task.task import Task

logger = logging.getLogger('GenerateThumbnailsTask')

BATCH_SIZE = 200
FLAG = 'thumbnails_dirty'


def _render_missing(path: str, specs: list[ImageTypeSpec]) -> list[tuple[int, bytes]] | None:
    """Runs in a worker process (must be picklable, hence module-level)."""
    from PIL import Image as PilImage

    try:
        with PilImage.open(path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.load()
            return [(type_id, render(img, fmt, w, h)) for type_id, fmt, w, h in specs]
    except Exception as e:
        logger.warning('Failed to generate thumbnails for %s: %s', path, e)
        return None


class GenerateThumbnailsTask(Task):
    def __init__(self, project, clear_flag: bool = True, type_ids: list[int] | None = None):
        super().__init__()
        self.name = 'Generate Thumbnails'
        self._project = project
        self._clear_flag = clear_flag
        #: when given, generate exactly these types instead of the auto_gen ones
        self._type_ids = type_ids
        self.max_workers = min(os.cpu_count() or 4, 10)

    def start(self):
        all_types = self._project.get_image_types()
        if self._type_ids is None:
            types = [t for t in all_types if t.auto_gen]
        else:
            wanted = set(self._type_ids)
            types = [t for t in all_types if t.id in wanted]
        if not types:
            logger.info('No image type to generate — nothing to do')
            self._clear()
            return

        # one query for every local path, instead of one connection per sha1
        paths = self._project.get_local_paths()
        sha1s = list(paths)
        self.state.total = len(sha1s)
        self._notify()
        if not sha1s:
            self._clear()
            return

        specs = {t.id: (t.id, t.format, t.width, t.height) for t in types}
        generated = 0
        with ProcessPoolExecutor(max_workers=self.max_workers) as pool:
            for start in range(0, len(sha1s), BATCH_SIZE):
                if self._cancel_event.is_set():
                    return
                batch = sha1s[start:start + BATCH_SIZE]
                existing = self._project.get_image_keys(batch)

                todo = []
                for sha1 in batch:
                    missing = [specs[t.id] for t in types if (t.id, sha1) not in existing]
                    if missing:
                        todo.append((sha1, missing))
                    else:
                        self.state.done += 1

                images: list[Image] = []
                futures = [pool.submit(_render_missing, paths[sha1], missing)
                           for sha1, missing in todo]
                for (sha1, _), future in zip(todo, futures):
                    rendered = future.result()
                    if rendered is None:
                        self.state.failed += 1
                    else:
                        images.extend(Image(type_id=type_id, sha1=sha1, data=data)
                                      for type_id, data in rendered)
                    self.state.done += 1

                if images:
                    self._project.upsert_images(images)
                    generated += len(images)
                self._notify()

        logger.info('Generated %d thumbnail(s) for %d sha1(s)', generated, len(sha1s))
        self._clear()

    def _clear(self):
        if not self._clear_flag:
            return
        with ProjectDB(self._project.project_db_path) as db:
            db.set_flag(FLAG, False)
