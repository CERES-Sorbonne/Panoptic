"""Panoptic legacy -> multi-database migrator (standalone, stdlib only).

Vendored from the standalone `migration-panpoic` tool. This package never
imports `panoptic` and has no third-party dependencies; keep it that way so it
stays syncable from upstream (see `scripts/sync_migrator.sh`).
"""

__version__ = "0.1.0"

#: Where this package was vendored from, and when. The upstream folder is not a
#: git repository, so there is no commit sha to record -- the date of the last
#: `scripts/sync_migrator.sh` run is the only drift marker available.
MIGRATOR_UPSTREAM = {
    "path": "/Users/david/migration-panpoic/migrator",
    "commit": None,          # upstream is not a git repository
    "synced_at": "2026-09-08",
}

SHAPES = ("P0", "P1", "v1", "v2", "v3_v4", "v5", "v6", "v7a", "v7b", "v7c")
