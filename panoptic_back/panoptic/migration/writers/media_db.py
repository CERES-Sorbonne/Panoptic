"""media.db -- thumbnails, atlas and maps. No journal, no sequence, no undo.

Vectors (MAPPING 7.1/7.2, user decision 2026-09-19): **kept for v7 sources**,
dropped for everything older. When `ir.vector_source` is set, `vector_types` is
a column copy (NULL source -> 'unknown', NULL params -> {} -- already done by the
reader) with `params` serialised exactly as the target's `EntitySchema` does
(`json.dumps(dict)`), and `vectors` is a **byte copy** streamed from the
read-only source: the legacy blob is raw float32 `tobytes()`, which is what the
target's `np.frombuffer(float32)` reads. Validation per row (skipped and
reported, never written): the type must exist, `data` must be a non-empty BLOB
that is a whole number of float32s and has its type's expected length, and the
sha1 must belong to a migrated instance. Otherwise both tables are left empty
and the new Panoptic recomputes them; the drop count is in `ir.dropped`.

The one real transform here is the thumbnail **pivot** (MAPPING 7.3): legacy
stores three fixed blob columns per sha1, the target one row per (type, sha1)
under a named, dimensioned `image_types` row. Sizes come from the legacy
`project` kv (`image_<name>_size`); shapes that have no such table (P0/P1/v1/v2,
and v7b whose `_project` is always empty) leave `width`/`height` NULL, which the
schema allows -- inventing the target's own 256/1024 defaults would be a lie
about what the user had configured.

A size the user had switched off (`save_image_<name> = false`) gets
`auto_gen = 0`, so post-migration imports do not start generating a size the
project never wanted. Writing any `image_types` row at all also means
`Project._ensure_default_image_types()` takes its existing-project branch and
never overwrites our sizes with 256/1024.
"""

from __future__ import annotations

import json
import os
import shutil

from ..readers.base import iter_legacy_vectors
from ..schema import create_db

#: rows per `executemany` when streaming vectors
VECTOR_BATCH = 1000

#: legacy thumbnail column -> the `project` kv keys that describe it
THUMBNAIL_SIZES = (("small",  "image_small_size",  "save_image_small"),
                   ("medium", "image_medium_size", "save_image_medium"),
                   ("large",  "image_large_size",  "save_image_large"))


class MediaDbWriter:
    def __init__(self, path, ir, source_dir=None, target_dir=None, report=None):
        self.path = path
        self.ir = ir
        self.source_dir = source_dir
        self.target_dir = target_dir or os.path.dirname(path)
        self.report = report
        self.conn = None
        self.stats = {}
        self.skipped = {}
        self.image_type_ids = {}
        self.vector_skips = 0

    def _skip(self, reason, n=1):
        self.skipped[reason] = self.skipped.get(reason, 0) + n

    def write(self):
        self.conn = create_db(self.path, "media")
        try:
            self.write_image_types()
            self.write_images()
            self.write_atlas()
            self.write_maps()
            self.write_vector_types()
            self.write_vectors()
            self.conn.commit()
        finally:
            self.conn.close()
            self.conn = None
        return self.stats

    # -- vectors (v7 only) ---------------------------------------------
    def write_vector_types(self):
        n = 0
        if self.ir.vector_source is not None:
            for vt in self.ir.vector_types:
                # the target's EntitySchema encodes a `dict` field with a plain
                # `json.dumps(value)` (entity_schema.py `_to_row`); match it
                self.conn.execute(
                    "INSERT INTO vector_types (id, source, params) VALUES (?,?,?)",
                    (vt.id, vt.source, json.dumps(vt.params)))
                n += 1
        self.stats["vector_types"] = n

    def write_vectors(self):
        """Stream-copy the legacy vectors, validating each row (MAPPING 7.2)."""
        self.vector_skips = 0
        src = self.ir.vector_source
        if src is None:
            self.stats["vectors"] = 0
            return
        types = {vt.id for vt in self.ir.vector_types}
        sha1s = {i.sha1 for i in self.ir.instances}
        lengths = src.lengths
        batch, n = [], 0
        sql = "INSERT INTO vectors (type_id, sha1, data) VALUES (?,?,?)"
        for type_id, sha1, data in iter_legacy_vectors(src.path):
            reason = None
            if type_id not in types:
                reason = "vector whose type_id is not a vector_type"
            elif not isinstance(data, bytes) or not data:
                reason = "vector whose data is NULL, empty or not a BLOB"
            elif len(data) % 4:
                reason = "vector whose byte length is not a multiple of 4"
            elif len(data) != lengths.get(type_id):
                reason = "vector whose length differs from its type's"
            elif not sha1 or sha1 not in sha1s:
                reason = "vector for a sha1 with no migrated instance"
            if reason:
                self._skip(reason)
                self.vector_skips += 1
                continue
            batch.append((type_id, sha1, data))
            if len(batch) >= VECTOR_BATCH:
                self.conn.executemany(sql, batch)
                n += len(batch)
                batch = []
        if batch:
            self.conn.executemany(sql, batch)
            n += len(batch)
        self.stats["vectors"] = n

    # -- thumbnails ----------------------------------------------------
    def _wanted_types(self):
        params = self.ir.project_params
        present = {name: any(getattr(t, name) for t in self.ir.thumbnails)
                   for name, _, _ in THUMBNAIL_SIZES}
        wanted = []
        for name, size_key, save_key in THUMBNAIL_SIZES:
            save = params.get(save_key)
            if not present[name] and save is not True:
                continue            # nothing stored and not switched on: skip
            size = params.get(size_key)
            size = int(size) if isinstance(size, (int, float)) else None
            wanted.append((name, size, 1 if save is not False else 0))
        return wanted

    def write_image_types(self):
        next_id = 1
        for name, size, auto_gen in self._wanted_types():
            self.conn.execute(
                "INSERT INTO image_types (id, name, format, width, height, "
                "auto_gen) VALUES (?,?,?,?,?,?)",
                (next_id, name, "jpeg", size, size, auto_gen))
            self.image_type_ids[name] = next_id
            next_id += 1
        self.stats["image_types"] = len(self.image_type_ids)

    def write_images(self):
        n = 0
        for thumb in self.ir.thumbnails:
            for name in self.image_type_ids:
                blob = getattr(thumb, name)
                if not blob:
                    continue          # NULL or zero-length: nothing to store
                self.conn.execute(
                    "INSERT OR IGNORE INTO images (type_id, sha1, data) "
                    "VALUES (?,?,?)",
                    (self.image_type_ids[name], thumb.sha1, blob))
                n += 1
        self.stats["images"] = n

    # -- atlas ---------------------------------------------------------
    def write_atlas(self):
        n = sheets = 0
        for a in self.ir.atlas:
            self.conn.execute(
                "INSERT INTO image_atlas (id, atlas_nb, width, height, "
                "cell_width, cell_height, sha1_mapping) VALUES (?,?,?,?,?,?,?)",
                (a.id, a.atlas_nb, a.width, a.height, a.cell_width,
                 a.cell_height, a.sha1_mapping if a.sha1_mapping is not None else "{}"))
            n += 1
            sheets += self.copy_atlas_sheets(a)
        self.stats["image_atlas"] = n
        self.stats["atlas_sheets"] = sheets

    def copy_atlas_sheets(self, atlas):
        """`image_data/atlas/<id>/atlas_<n>.png` -> `atlas/<id>_<n>.png`.

        The row is useless without the sheet: `get_atlas_sheet` serves the new
        path. Pure cache, so a missing sheet is reported, not fatal.
        """
        if not self.source_dir:
            return 0
        src_dir = os.path.join(self.source_dir, "image_data", "atlas", str(atlas.id))
        if not os.path.isdir(src_dir):
            self._skip("atlas sheets missing on disk")
            return 0
        dest_dir = os.path.join(self.target_dir, "atlas")
        os.makedirs(dest_dir, exist_ok=True)
        copied = 0
        for nb in range(atlas.atlas_nb or 0):
            src = os.path.join(src_dir, "atlas_%d.png" % nb)
            if not os.path.isfile(src):
                self._skip("atlas sheet missing on disk")
                continue
            shutil.copy2(src, os.path.join(dest_dir, "%d_%d.png" % (atlas.id, nb)))
            copied += 1
        return copied

    # -- maps ----------------------------------------------------------
    def write_maps(self):
        known = {i.id for i in self.ir.instances}
        n = 0
        for m in self.ir.maps:
            # `data` is a flat JSON array embedding instance ids; it is copied
            # verbatim and is valid ONLY because instance ids are preserved.
            if m.data:
                for inst_id in _map_instance_ids(m.data):
                    if inst_id not in known:
                        self._skip("map referencing an unknown instance")
                        break
            self.conn.execute(
                "INSERT INTO maps (id, source, name, key, count, data) "
                "VALUES (?,?,?,?,?,?)",
                (m.id, m.source or "", m.name or "", m.key or "",
                 m.count if m.count is not None else 0, m.data))
            n += 1
        self.stats["maps"] = n


def _map_instance_ids(data):
    """The instance ids embedded in a `maps.data` blob, best effort."""
    try:
        parsed = json.loads(data) if isinstance(data, (str, bytes)) else data
    except ValueError:
        return []
    if not isinstance(parsed, list):
        return []
    if parsed and isinstance(parsed[0], list):
        return [row[0] for row in parsed if row and isinstance(row[0], int)]
    return [v for v in parsed[::3] if isinstance(v, int)]


def write_media_db(path, ir, source_dir=None, target_dir=None, report=None):
    w = MediaDbWriter(path, ir, source_dir, target_dir, report)
    return w, w.write()
