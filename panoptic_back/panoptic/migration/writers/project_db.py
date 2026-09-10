"""project.db -- `id_registry`, `project_config`, `user_defaults`.

Written **last**, because the whole point of `id_registry` is to be
`MAX(id) + 1` over the rows that were actually written, and ID_STRATEGY 2.2 says
to compute it from the *output*, not from the legacy table: they agree under the
preserve-ids policy, and computing from the output is the check that cannot
drift.

The three keys of `project_config` are a `KeyValueSchema` over the `ProjectConfig`
struct. `id` is a fresh UUID and **must equal** `projects.id` in the panoptic home
DB or `load_project` refuses to open the folder -- task 3.4 writes the other half,
so the id is returned to the pipeline rather than invented twice.

Not written here: `tab_data` (tabs and all UI data are dropped, signed off) and
`plugin_data`, which is dead code upstream and whose `plugin_id INTEGER` cannot
even hold `plugins.id TEXT`. Plugin params live in `user_defaults` now.
"""

from __future__ import annotations

import json
import sqlite3
import uuid

from ..schema import create_db
from .ids import ID_REGISTRY_KEYS, REGISTRY_TABLES, next_free

DEFAULT_USER_ID = "default"
#: `plugin_data` keys that are not `<PluginName>.base` have no addressable owner
LEGACY_PLUGIN_BUCKET = "legacy.plugin_data"


def max_id(conn, table):
    row = conn.execute("SELECT MAX(id) FROM %s" % table).fetchone()
    return row[0]


def registry_seeds(data_path, media_path):
    """The 11 counters, computed from the written DBs. All 11, never NULL."""
    conns = {"data": sqlite3.connect("file:%s?mode=ro" % data_path, uri=True),
             "media": sqlite3.connect("file:%s?mode=ro" % media_path, uri=True)}
    try:
        seeds = {}
        for key in ID_REGISTRY_KEYS:
            db, table = REGISTRY_TABLES[key]
            seeds[key] = next_free(max_id(conns[db], table))
        return seeds
    finally:
        for conn in conns.values():
            conn.close()


class ProjectDbWriter:
    def __init__(self, path, ir, data_path, media_path, name=None,
                 description=None, project_id=None, system=None, report=None):
        self.path = path
        self.ir = ir
        self.data_path = data_path
        self.media_path = media_path
        self.name = name
        self.description = description
        self.project_id = project_id or str(uuid.uuid4())
        self.system = system          # SystemPropertyPlan, for the id remap
        self.report = report
        self.stats = {}
        self.notes = []

    def write(self):
        conn = create_db(self.path, "project")
        try:
            seeds = registry_seeds(self.data_path, self.media_path)
            for key in ID_REGISTRY_KEYS:
                # json.dumps: `allocate()` uses get_key(), which does NOT fall
                # back to the struct default -- a NULL here raises TypeError.
                # (`value JSON` has NUMERIC affinity, so sqlite stores the text
                # '13' as the integer 13. `get_key` returns non-strings as-is,
                # so both round-trip; upstream's own writes behave the same.)
                conn.execute("INSERT INTO id_registry (key, value) VALUES (?,?)",
                             (key, json.dumps(int(seeds[key]))))
            self.stats["id_registry"] = dict(seeds)

            for key, value in (("id", self.project_id), ("name", self.name),
                               ("description", self.description)):
                conn.execute("INSERT INTO project_config (key, value) VALUES (?,?)",
                             (key, json.dumps(value) if value is not None else None))

            # The migrated media DB carries whatever thumbnails the legacy DB
            # had -- often none, or only some sizes. The flag makes the target
            # backfill the rest from the original files on first open
            # (GenerateThumbnailsTask), so no re-import is needed.
            conn.execute("INSERT OR REPLACE INTO project_flags (key, value) VALUES (?,?)",
                         ("thumbnails_dirty", json.dumps(True)))
            self.stats["thumbnails_dirty"] = True

            self.stats["user_defaults"] = self.write_user_defaults(conn)
            conn.commit()
        finally:
            conn.close()
        return self.stats

    def write_user_defaults(self, conn):
        n = 0
        for plugin, params in sorted(self.ir.plugin_params.items()):
            params = self.remap_property_ids(params, "plugin %s params" % plugin)
            conn.execute("INSERT OR REPLACE INTO user_defaults "
                         "(user_id, key, data) VALUES (?,?,?)",
                         ("plugin.%s" % plugin, "params", json.dumps(params)))
            n += 1
        for key, value in sorted(self.ir.orphan_plugin_data.items()):
            value = self.remap_property_ids(value, "legacy plugin_data %r" % key)
            conn.execute("INSERT OR REPLACE INTO user_defaults "
                         "(user_id, key, data) VALUES (?,?,?)",
                         (LEGACY_PLUGIN_BUCKET, key, json.dumps(value)))
            n += 1
        return n

    # -- negative property ids inside opaque blobs (ID_STRATEGY 4.2) ----
    def remap_property_ids(self, value, where):
        """Rewrite legacy computed property ids in a carried-across blob.

        Legacy computed properties were virtual, with negative ids; nothing in
        the target resolves a negative property id, so carrying one across
        silently is not an option. Only values under a key that names a property
        are touched, `-3` (average hash) is dropped, and every occurrence is
        reported either way.
        """
        if self.system is None:
            return value
        return self._walk(value, where, False)

    def _walk(self, value, where, in_prop_key):
        if isinstance(value, dict):
            return {k: self._walk(v, where, _is_property_key(k))
                    for k, v in value.items()}
        if isinstance(value, list):
            out = []
            for item in value:
                new = self._walk(item, where, in_prop_key)
                if new is not None or item is None:
                    out.append(new)
            return out
        if isinstance(value, bool) or not isinstance(value, int):
            return value
        if value >= 0:
            return value
        if not in_prop_key:
            self.notes.append("%s holds a negative id %d under a key that does "
                              "not name a property: left as-is" % (where, value))
            return value
        new = self.system.remap_legacy_computed(value)
        if new is None:
            self.notes.append("%s referenced legacy computed property %d, which "
                              "has no target: dropped" % (where, value))
        else:
            self.notes.append("%s: legacy computed property %d remapped to the "
                              "new system property %d" % (where, value, new))
        return new


def _is_property_key(key):
    key = str(key).lower()
    return "propert" in key or key in ("prop", "prop_id", "prop_ids")


def write_project_db(path, ir, data_path, media_path, **kwargs):
    w = ProjectDbWriter(path, ir, data_path, media_path, **kwargs)
    return w, w.write()
