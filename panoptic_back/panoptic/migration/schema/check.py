"""Advisory check: has the copied schema drifted from `~/panoptic`?

The copy in this package is a snapshot. Upstream is a git branch that can move.
A migrator that silently writes a stale schema is worse than one that says so,
but a *hard* dependency on a checkout being present would break the "standalone,
stdlib-only" rule -- so this is deliberately advisory:

* it needs no panoptic install and no imports (msgspec is not available here);
  it hashes the upstream **source files** that determine the schema;
* it is skipped, silently, when no checkout is found;
* a mismatch produces a warning in the run report, never an error.

`upstream.json` records the sha256 of every file that can change the generated
DDL: the four `create.py`, their `models.py`, `entity_schema.py`,
`key_value_shema.py` and `system_properties.py`. Refresh it (and the `.sql`
copies) with `python3 -m migrator.schema.regenerate`.
"""

from __future__ import annotations

import hashlib
import json
import os

from . import SCHEMA_DIR

MANIFEST = os.path.join(SCHEMA_DIR, "upstream.json")

DEFAULT_ROOTS = ("~/panoptic/panoptic_back", "~/panoptic")

#: relative to <root>/panoptic/core/databases (+ the two outside it)
UPSTREAM_FILES = (
    "panoptic/core/databases/entity_schema.py",
    "panoptic/core/databases/key_value_shema.py",
    "panoptic/core/databases/panoptic/create.py",
    "panoptic/core/databases/panoptic/models.py",
    "panoptic/core/databases/project/create.py",
    "panoptic/core/databases/project/models.py",
    "panoptic/core/databases/data/create.py",
    "panoptic/core/databases/data/models.py",
    "panoptic/core/databases/data/system_properties.py",
    "panoptic/core/databases/media/create.py",
    "panoptic/core/databases/media/models.py",
)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def find_upstream(root=None):
    """Locate a `rework-front` checkout, or return None."""
    candidates = [root] if root else list(DEFAULT_ROOTS)
    for cand in candidates:
        if not cand:
            continue
        path = os.path.abspath(os.path.expanduser(cand))
        if os.path.isfile(os.path.join(path, UPSTREAM_FILES[0])):
            return path
    return None


def fingerprint(root):
    return {rel: sha256_file(os.path.join(root, rel))
            for rel in UPSTREAM_FILES
            if os.path.isfile(os.path.join(root, rel))}


def load_manifest():
    try:
        with open(MANIFEST, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError:
        return {}


def check_upstream(root=None):
    """Return a (possibly empty) list of advisory warning strings."""
    manifest = load_manifest()
    recorded = manifest.get("files", {})
    root = find_upstream(root)
    if root is None:
        return []                      # no checkout here: nothing to compare
    live = fingerprint(root)
    changed = sorted(rel for rel, digest in recorded.items()
                     if rel in live and live[rel] != digest)
    missing = sorted(rel for rel in recorded if rel not in live)
    added = sorted(rel for rel in live if rel not in recorded)
    out = []
    if changed:
        out.append(
            "target schema sources changed upstream since migrator/schema/ was "
            "captured (%s): the copied CREATE TABLE SQL may be stale -- re-run "
            "`python3 -m migrator.schema.regenerate` and re-read "
            "analysis/target_schema.sql. Advisory only."
            % ", ".join(os.path.basename(os.path.dirname(c)) + "/" +
                        os.path.basename(c) for c in changed))
    if missing:
        out.append("target schema source(s) gone upstream: %s" % ", ".join(missing))
    if added:
        out.append("new target schema source(s) upstream, not in the manifest: %s"
                   % ", ".join(added))
    return out
