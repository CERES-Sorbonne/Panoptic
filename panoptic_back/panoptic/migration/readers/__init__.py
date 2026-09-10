"""Legacy readers: any of the 11 source shapes -> one intermediate representation.

Task 3.2.


Why normalise-then-convert, and where it stops
==============================================

The plan of record is *normalise every source up to the v7c shape, then convert
v7c to the new format exactly once*. That is the right shape for the project
because it keeps the expensive, lossy, hard-to-verify half of the work --
`analysis/MAPPING.md`'s 25-table mapping onto four new databases -- written
once, against one schema, instead of eleven times.

But it is a **conceptual** normalisation, done in memory while reading, not a
sequence of `ALTER TABLE`s replayed against a copy of the source. Three reasons:

1. **The upstream chain does not reach.** `migrations/v*.py` starts at `v3_sql`.
   P0, P1, v1 and v2 have no upstream path at all -- there has never been a
   v1->v2 script, and the pre-versioned eras predate the migration system
   entirely. Four of the eleven shapes must be read bespoke regardless
   (`readers/prehistoric.py` for P0/P1, `readers/modern.py` for v1/v2), so
   replaying SQL would buy a uniform path for only part of the range.

2. **One step of the upstream chain destroys data.** `v7_sql` is
   `DROP TABLE IF EXISTS vectors;` followed by a `CREATE` of the empty
   re-keyed table -- the v6->v7 migration deletes every vector rather than
   converting it (MAPPING U1). Replaying the chain on a v1-v6 project would
   silently destroy the vector store on the way to "v7". (Vectors are dropped
   by user sign-off now, so this no longer *costs* us anything -- but it is
   exactly the kind of surprise that argues against replaying migrations you
   did not write.)

3. **The rest of the chain is a no-op for a reader.** `v3_sql` rebuilds
   `instances` with identical columns to add a foreign key (and leaves an
   `instances_old` copy behind, MAPPING U10); `v5_sql` adds a nullable column,
   which a reader sees as `None` anyway; `v6_sql` creates indexes. Only
   `v4_sql` changes a *value* -- `type='string'` -> `'text'` -- and that one is
   applied, defensively, to every shape (`base.normalise_dtype`), because a
   v1/v2 DB mis-stamped `db_version = 4` by the broken 0.4.x upgrade path never
   had it run.

So: the migrations are copied into `migrator/legacy/` as the authority for what
each step means (and are asserted against in the tests), the one value-changing
step is reimplemented as a pure function, and the readers produce the *result*
of the normalisation directly. Nothing is ever written to the source -- the
connection is opened `mode=ro` (CLAUDE.md rule 1).

Quirks normalised on the way in
-------------------------------
Each of these would otherwise reach the writers as corrupt-looking data:

* `tags.parents` root sentinel `[0]` (P0/P1/v1/v2) -> `[]`. Keeping it invents
  a phantom tag id 0 that resolves to nothing.
* `properties.type = 'string'` -> `'text'` (the v4 rename), everywhere.
* P0's `images.paths` read as a **folder id**, not a path.
* P0/P1's `url = '/images/<abspath>'` -> `<abspath>`.
* P0's missing `properties.mode` -> `'sha1'` for every property.
* P1's `property_values.image_id = -1` sentinel -> the sha1-scoped list.
* v7b's `_project` (misnamed, and always empty) read anyway, with a warning.
* Tag values exploded one row per tag id, routed on **dtype first**, never
  left as a JSON list in the generic value tables.

Dropped by user sign-off (CLAUDE.md): tabs and all UI data, vectors,
`raw_images`. Their *counts* are recorded in `ProjectIR.dropped` so every run
report states the loss; their payloads never enter the IR.
"""

from __future__ import annotations

from ..errors import UnknownShape
from .base import Reader
from .modern import ModernReader, V7Reader
from .prehistoric import P0Reader, P1Reader

__all__ = ["READERS", "reader_for", "read_source",
           "P0Reader", "P1Reader", "ModernReader", "V7Reader"]

#: shape -> reader class. Every branch `detect.sniff()` can return is here.
READERS = {}
for _cls in (P0Reader, P1Reader, ModernReader, V7Reader):
    for _shape in _cls.shapes:
        READERS[_shape] = _cls


def reader_for(shape):
    try:
        return READERS[shape]
    except KeyError:
        raise UnknownShape("no reader for source shape %r (known: %s)"
                           % (shape, ", ".join(sorted(READERS))))


def read_source(detection, db_path, project_dir=None, with_blobs=True,
                stat_files=True):
    """Read a legacy project DB into a `ProjectIR`. Never writes to it.

    `detection` is what `migrator.detect.detect_db` returned. `with_blobs=False`
    skips thumbnail payloads (useful for a counts-only pass over a huge
    project); `stat_files=False` skips the `created_at` filesystem walk.
    """
    cls = reader_for(detection.shape)
    return cls(db_path, detection.shape, detection.variant,
               project_dir=project_dir, with_blobs=with_blobs,
               stat_files=stat_files).read()
