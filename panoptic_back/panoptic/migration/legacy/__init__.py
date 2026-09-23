"""Verbatim copies of panoptic's own `project_db/migrations/v*.py`.

Copied from `~/panoptic` at `main` (commit 6878be80ef9ab3b67660f7e5429d375fc49ede6b)
on 2026-09-07. Copied, never imported from `~/panoptic` at runtime: the
migrator must run on a machine that has no panoptic checkout and no panoptic
install.

They are kept here as the **authority for what each version step means**, and
as a diffable record if upstream ever changes them. Only one of the five is
actually executed as a transform, because a *reader* does not need the other
four -- see `migrator/readers/__init__.py` for the full argument:

===== ============================================ =========================
step   what the upstream SQL does                   what the reader does
===== ============================================ =========================
v3     rebuilds `instances` (adds a FK, leaves an   nothing: no column or
       `instances_old` copy behind)                 value changes. The stray
                                                    `instances_old` table is
                                                    ignored (MAPPING U10).
v4     `UPDATE properties SET type="text"           APPLIED, defensively, to
       WHERE type="string"`                         every shape (MAPPING U3).
v5     `ALTER TABLE properties ADD COLUMN           nothing: a missing column
       property_group_id`                           reads as None.
v6     creates three indexes                        nothing: indexes are not
                                                    data.
v7     **`DROP TABLE IF EXISTS vectors`** then      NEVER RUN. It destroys
       recreates it empty                           every vector (MAPPING U1).
===== ============================================ =========================

`V4_STRING_TO_TEXT` below is the reader's executable form of `v4_sql`; it is
asserted against the copied SQL by `migrator/tests/test_readers.py`, so the two
cannot drift apart.
"""

from .v3 import v3_sql
from .v4 import v4_sql
from .v5 import v5_sql
from .v6 import v6_sql
from .v7 import v7_sql

__all__ = ["v3_sql", "v4_sql", "v5_sql", "v6_sql", "v7_sql",
           "V4_STRING_TO_TEXT", "UPSTREAM_COMMIT"]

UPSTREAM_COMMIT = "6878be80ef9ab3b67660f7e5429d375fc49ede6b"

#: The v4 migration, as a pure value rewrite. Equivalent to `v4_sql`.
V4_STRING_TO_TEXT = {"string": "text"}
