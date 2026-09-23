"""Refresh `upstream.json` from a local `~/panoptic` checkout.

Run by hand, never during a migration:

    python3 -m migrator.schema.regenerate [PATH_TO_panoptic_back]

The `.sql` copies themselves come from `analysis/target_schema.sql` (task 0.1),
which is produced by importing the target's `create.py` in an env that has
`msgspec` -- see `analysis/TARGET_NOTES.md`. This script only re-records the
fingerprints, and re-splits `analysis/target_schema.sql` when it is present.
"""

from __future__ import annotations

import json
import os
import re
import sys

from . import SCHEMA_DIR
from .check import MANIFEST, find_upstream, fingerprint

_LABELS = {"panoptic.db": "panoptic", "project.db": "project",
           "data DB": "data", "media DB": "media"}
_HEADER = ("-- %s -- CREATE TABLE SQL copied verbatim from the target's own create.py\n"
           "-- (~/panoptic @ rework-front, via analysis/target_schema.sql, task 0.1).\n"
           "-- Regenerate with: python3 -m migrator.schema.regenerate\n"
           "-- Do not hand-edit: migrator/schema/check.py hashes the upstream sources.\n\n")


def split_target_schema(path):
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    parts = re.split(r"^-- =+\n-- DATABASE: (.+?)   version.*?\n(?:--.*\n)*-- =+\n",
                     src, flags=re.M)
    written = []
    for i in range(1, len(parts), 2):
        name = _LABELS[parts[i].strip()]
        body = re.split(r"^-- =+\n-- NOT IN create\.py", parts[i + 1], flags=re.M)[0]
        out = os.path.join(SCHEMA_DIR, "%s.sql" % name)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(_HEADER % name + body.strip() + "\n")
        written.append(out)
    return written


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = find_upstream(argv[0] if argv else None)
    if root is None:
        print("no ~/panoptic checkout found; nothing to fingerprint", file=sys.stderr)
        return 1
    dump = os.path.join(os.path.dirname(os.path.dirname(SCHEMA_DIR)),
                        "analysis", "target_schema.sql")
    if os.path.isfile(dump):
        for path in split_target_schema(dump):
            print("wrote %s" % path)
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump({"root": root, "files": fingerprint(root)}, fh,
                  indent=2, sort_keys=True)
        fh.write("\n")
    print("wrote %s" % MANIFEST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
