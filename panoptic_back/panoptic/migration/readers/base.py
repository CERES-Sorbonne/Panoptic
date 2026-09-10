"""Shared machinery for every legacy reader.

`Reader` implements the parts that are identical across all 11 shapes -- the
read-only connection, the quirk normalisers, the value router, the integrity
checks -- and leaves the shape-specific table reads to subclasses.
"""

from __future__ import annotations

import datetime
import errno
import json
import os

from ..detect import open_readonly
from ..ir import (AtlasSheet, Dropped, Folder, Instance, MapRow, ProjectIR,
                  Property, PropertyGroup, Tag, Thumbnail, Value)
from ..legacy import V4_STRING_TO_TEXT

#: P0/P1 serve images over HTTP and store the served URL, not the path
#: (MAPPING U6). `scripts/convert_old_db.py` on `main` does the same `[8:]`.
SERVED_URL_PREFIX = "/images/"

#: The pre-v3 root-tag sentinel. A root tag's parents are `[0]` before v3 and
#: `[]` from v3 on; tag id 0 has never existed (MAPPING U4 / §5.2).
ROOT_PARENT_SENTINEL = 0


# --------------------------------------------------------------------------
# small pure helpers
# --------------------------------------------------------------------------

def json_loads(raw, default=None):
    """Decode a legacy JSON column. Legacy wrote plenty of NULLs and junk."""
    if raw is None or raw == "":
        return default
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return default
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def normalise_dtype(dtype):
    """Apply `migrator/legacy/v4.py` (`type='string'` -> `'text'`) defensively.

    Upstream ran this once, at v4. We run it on every shape because a v1/v2 DB
    mis-stamped `db_version = 4` by the broken 0.4.x upgrade path never had it
    applied, and `'string'` is not a dtype the target understands (MAPPING U3).
    """
    if dtype is None:
        return None
    return V4_STRING_TO_TEXT.get(dtype, dtype)


def normalise_parents(raw):
    """Legacy `tags.parents` JSON -> a clean list of int tag ids.

    Strips the pre-v3 root sentinel `0` wherever it appears, so `[0]` becomes
    `[]` and a (never observed, but cheap to guard) `[0, 3]` becomes `[3]`.
    Keeping the 0 would invent a phantom tag that resolves to nothing.
    """
    parents = json_loads(raw, default=[])
    if not isinstance(parents, list):
        return []
    out = []
    for p in parents:
        try:
            p = int(p)
        except (TypeError, ValueError):
            continue
        if p != ROOT_PARENT_SENTINEL and p not in out:
            out.append(p)
    return out


def normalise_color(raw):
    """`tags.color` is TEXT in legacy and INTEGER in the target (MAPPING §5.2)."""
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def strip_served_url(url):
    """`/images/<abspath>` -> `<abspath>` for the P0/P1 eras."""
    if isinstance(url, str) and url.startswith(SERVED_URL_PREFIX):
        return url[len(SERVED_URL_PREFIX):]
    return url


def file_created_at(path, errors=None):
    """`files.created_at` from the file's mtime (CLAUDE.md L11 sign-off).

    This is the default behaviour, not a flag. Missing file -> None, which the
    target stores as NULL. The format is what sqlite3's built-in timestamp
    converter accepts. `errors`, when given, is a dict that collects the
    `errno` of every failed stat, so the caller can tell "gone" from
    "unreadable" (macOS TCC-protected folders raise EPERM, not ENOENT).
    """
    if not path:
        return None
    try:
        st = os.stat(path)
    except OSError as exc:
        if errors is not None:
            errors[exc.errno] = errors.get(exc.errno, 0) + 1
        return None
    return datetime.datetime.fromtimestamp(st.st_mtime).strftime(
        "%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------
# the base reader
# --------------------------------------------------------------------------

class Reader:
    """Base class. Subclasses fill `ir` from their own shape's tables.

    Subclass contract: implement `read_entities()`. Everything else -- opening
    the DB read-only, the shared media/plugin tables, normalisation and the
    integrity pass -- happens here.
    """

    #: shapes this reader claims, for the registry in `__init__.py`
    shapes = ()

    def __init__(self, db_path, shape, variant="", project_dir=None,
                 with_blobs=True, stat_files=True):
        self.db_path = db_path
        self.shape = shape
        self.variant = variant or shape
        self.project_dir = project_dir or os.path.dirname(os.path.abspath(db_path))
        self.with_blobs = with_blobs
        self.stat_files = stat_files
        self.conn = None
        self.tables = set()
        self.ir = ProjectIR(shape=shape, variant=self.variant, dropped=Dropped())

    # -- plumbing ---------------------------------------------------------
    def warn(self, msg):
        self.ir.warnings.append(msg)

    def has(self, table):
        return table in self.tables

    def rows(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def scalar(self, sql, params=(), default=None):
        row = self.conn.execute(sql, params).fetchone()
        if row is None or row[0] is None:
            return default
        return row[0]

    def count(self, table):
        if not self.has(table):
            return 0
        return int(self.scalar("SELECT COUNT(*) FROM %s" % table, default=0))

    # -- entry point ------------------------------------------------------
    def read(self):
        self.conn = open_readonly(self.db_path)
        try:
            self.tables = {
                r[0] for r in self.conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")
            }
            self.read_entities()
            self.read_media()
            self.read_params()
            self.record_drops()
        finally:
            self.conn.close()
            self.conn = None
        self.finalise()
        return self.ir

    # -- to be provided by the subclass -----------------------------------
    def read_entities(self):
        raise NotImplementedError

    # -- shared reads -----------------------------------------------------
    def read_folders(self):
        for r in self.rows("SELECT id, path, name, parent FROM folders"):
            self.ir.folders.append(
                Folder(id=r["id"], path=r["path"], name=r["name"],
                       parent=r["parent"]))

    def read_tags(self):
        for r in self.rows("SELECT id, property_id, value, parents, color FROM tags"):
            self.ir.tags.append(Tag(
                id=r["id"], property_id=r["property_id"], value=r["value"],
                parents=normalise_parents(r["parents"]),
                color=normalise_color(r["color"])))

    def read_property_groups(self):
        if not self.has("property_group"):
            return
        for r in self.rows("SELECT id, name FROM property_group"):
            self.ir.property_groups.append(PropertyGroup(id=r["id"], name=r["name"]))

    def read_media(self):
        """Thumbnail cache (v3+), atlas and maps (v7c). Vectors are DROPPED."""
        if self.has("images") and "small" in self._columns("images"):
            cols = self._columns("images")
            sel = ", ".join(c for c in ("sha1", "small", "medium", "large") if c in cols)
            for r in self.rows("SELECT %s FROM images" % sel):
                if self.with_blobs:
                    self.ir.thumbnails.append(Thumbnail(
                        sha1=r["sha1"],
                        small=r["small"] if "small" in cols else None,
                        medium=r["medium"] if "medium" in cols else None,
                        large=r["large"] if "large" in cols else None))
                else:
                    self.ir.thumbnails.append(Thumbnail(sha1=r["sha1"]))

        if self.has("atlas"):
            for r in self.rows("SELECT id, atlas_nb, width, height, cell_width, "
                               "cell_height, sha1_mapping FROM atlas"):
                self.ir.atlas.append(AtlasSheet(
                    id=r["id"], atlas_nb=r["atlas_nb"], width=r["width"],
                    height=r["height"], cell_width=r["cell_width"],
                    cell_height=r["cell_height"], sha1_mapping=r["sha1_mapping"]))

        if self.has("maps"):
            for r in self.rows("SELECT id, source, name, key, count, data FROM maps"):
                self.ir.maps.append(MapRow(
                    id=r["id"], source=r["source"], name=r["name"], key=r["key"],
                    count=r["count"], data=r["data"]))

    def read_params(self):
        """`project` kv + plugin params. Both are shape-conditional."""
        # v7b renamed `project` to `_project`; the release then queried the old
        # name, so `_project` is ALWAYS empty. Read it anyway -- correct, and it
        # costs nothing if a hand-patched DB ever has rows in it.
        for table in ("project", "_project"):
            if self.has(table):
                for r in self.rows("SELECT key, value FROM %s" % table):
                    self.ir.project_params[r["key"]] = json_loads(r["value"], r["value"])
                if table == "_project" and not self.ir.project_params:
                    self.warn("v7b `_project` is empty, as it always is (0.7.0 "
                              "writes the table but queries `project`): no "
                              "thumbnail sizes to migrate, defaults will apply")

        if self.has("plugin_data"):
            for r in self.rows("SELECT key, value FROM plugin_data"):
                key = r["key"]
                value = json_loads(r["value"], r["value"])
                if key.endswith(".base"):
                    self.ir.plugin_params[key[:-len(".base")]] = value
                elif "." not in key:
                    # 0.7.x fixtures store the bare plugin name.
                    self.ir.plugin_params[key] = value
                else:
                    self.ir.orphan_plugin_data[key] = value
        if self.has("plugin_defaults"):
            # v1 only; dropped upstream at v2 with no migration (MAPPING U2).
            for r in self.rows("SELECT name, base, functions FROM plugin_defaults"):
                self.ir.plugin_params[r["name"]] = json_loads(r["base"], {})
                funcs = json_loads(r["functions"], None)
                if funcs:
                    self.ir.orphan_plugin_data["%s.functions" % r["name"]] = funcs

    def record_drops(self):
        d = self.ir.dropped
        # tabs / ui data (L3)
        d.tabs += self.count("tabs")
        if self.has("ui_data"):
            for r in self.rows("SELECT key, value FROM ui_data"):
                d.ui_data_keys.append(r["key"])
                if r["key"] == "tabs":
                    tabs = json_loads(r["value"], [])
                    d.tabs += len(tabs) if isinstance(tabs, list) else 0
        # vectors (signed off: recompute in the new Panoptic)
        d.vectors += self.count("vectors")
        d.vector_types += self.count("vector_type")
        # raw_images (L6)
        if self.has("raw_images"):
            d.raw_images = self.count("raw_images")
            d.raw_image_bytes = int(self.scalar(
                "SELECT COALESCE(SUM(LENGTH(data)), 0) FROM raw_images", default=0))
        # panoptic.default_vector (L9)
        if self.has("panoptic"):
            d.default_vector = self.scalar(
                "SELECT value FROM panoptic WHERE key = 'default_vector'")
        # action_params (v1, L8): no target concept -- carry it into the report
        # verbatim so nothing is silently binned.
        if self.has("action_params"):
            for r in self.rows("SELECT name, value FROM action_params"):
                d.action_params[r["name"]] = json_loads(r["value"], r["value"])

    # -- helpers subclasses use -------------------------------------------
    def _columns(self, table):
        return {r[1] for r in self.conn.execute("PRAGMA table_info(%s)" % table)}

    def route_value(self, prop, key, raw, scope):
        """Send one legacy value row to the right IR list (MAPPING §4.2).

        Routing is on **dtype first, mode second**: a `tag`/`multi_tags` value
        explodes into junction rows and must never land in the generic value
        lists, or the target simply never reads it back.
        """
        value = json_loads(raw, None) if isinstance(raw, str) else raw
        if prop.is_tag:
            ids = value
            if isinstance(ids, int):
                ids = [ids]
            if not isinstance(ids, list):
                return
            for tag_id in ids:
                try:
                    tag_id = int(tag_id)
                except (TypeError, ValueError):
                    continue
                if scope == "instance":
                    self.ir.instance_tag_values.append((key, prop.id, tag_id))
                else:
                    self.ir.sha1_tag_values.append((key, prop.id, tag_id))
            return
        v = Value(property_id=prop.id, key=key, raw=raw, value=value)
        if scope == "instance":
            self.ir.instance_values.append(v)
        else:
            self.ir.sha1_values.append(v)

    def property_index(self):
        return {p.id: p for p in self.ir.properties}

    def stat_instances(self):
        """Fill `Instance.created_at` from the filesystem (L11 sign-off)."""
        if not self.stat_files:
            return
        by_folder = {f.id: f for f in self.ir.folders}
        missing = 0
        errors = {}
        for inst in self.ir.instances:
            folder = by_folder.get(inst.folder_id)
            path = os.path.join(folder.path, inst.name) if folder else inst.url
            inst.created_at = (file_created_at(path, errors)
                               or file_created_at(inst.url, errors))
            if inst.created_at is None:
                missing += 1
        if missing:
            denied = sum(n for e, n in errors.items()
                         if e in (errno.EPERM, errno.EACCES))
            why = "unreadable" if denied else "missing from disk"
            self.warn("%d/%d files are %s: created_at is NULL for "
                      "them (L11)%s" % (
                          missing, len(self.ir.instances), why,
                          "" if not denied
                          else " -- %d stat(s) were denied by the OS, so the "
                               "files may well still be there" % denied))

    # -- integrity --------------------------------------------------------
    def finalise(self):
        """Quirk-independent checks. Nothing in either schema enforces these."""
        ir = self.ir
        props = self.property_index()
        tags = {t.id: t for t in ir.tags}
        folders = {f.id: f for f in ir.folders}

        # url == folder.path + '/' + name (MAPPING §3.4 / L10). A mismatch means
        # the image will not resolve after migration.
        bad_url = 0
        for inst in ir.instances:
            folder = folders.get(inst.folder_id)
            if folder is None:
                bad_url += 1
                continue
            if inst.url and os.path.normpath(inst.url) != os.path.normpath(
                    os.path.join(folder.path, inst.name)):
                bad_url += 1
        if bad_url:
            self.warn("%d/%d instances have a url that is not "
                      "folder.path + '/' + name -- those images will not "
                      "resolve after migration; re-import the folder (L10)"
                      % (bad_url, len(ir.instances)))

        # dangling / cross-property tag parents
        dropped_parents = 0
        for tag in ir.tags:
            keep = []
            for p in tag.parents:
                parent = tags.get(p)
                if parent is None or parent.property_id != tag.property_id:
                    dropped_parents += 1
                    continue
                keep.append(p)
            tag.parents = keep
        if dropped_parents:
            self.warn("dropped %d dangling or cross-property tag parent(s)"
                      % dropped_parents)

        # tag assignments pointing at a tag that does not exist, or that belongs
        # to another property (legacy plugins could write either).
        for name, rows, tag_pos in (("instance_tag_values", ir.instance_tag_values, 2),
                                    ("sha1_tag_values", ir.sha1_tag_values, 2)):
            keep, bad = [], 0
            for row in rows:
                tag = tags.get(row[tag_pos])
                if tag is None or tag.property_id != row[1]:
                    bad += 1
                    continue
                keep.append(row)
            rows[:] = keep
            if bad:
                self.warn("dropped %d %s row(s) whose tag id is unknown or "
                          "belongs to another property" % (bad, name))

        # values for a property that no longer exists
        for name, rows in (("instance_values", ir.instance_values),
                           ("sha1_values", ir.sha1_values)):
            bad = [v for v in rows if v.property_id not in props]
            if bad:
                rows[:] = [v for v in rows if v.property_id in props]
                self.warn("dropped %d %s row(s) for an unknown property"
                          % (len(bad), name))

        # ahash is dropped everywhere (L1); count it so the report says so.
        ir.dropped.ahash = getattr(self, "ahash_count", 0)
