"""panoptic.db -- the *home* (instance) registry: `panoptic_config`, `users`,
`projects`, `plugins`  (task 3.4).

This is the other half of the invariant task 3.3 could only state:

    projects.id (here)  ==  project_config.id (in the folder's project.db)

`Panoptic.load_project` re-opens the folder's `project.db`, compares the two and
raises `ID mismatch` if they differ, so the registration can never invent an id
-- it must be *read back* from the migrated folder. Every entry point here takes
the id from a real `project.db`; none of them generate one.

Unlike the project writers this one is an **upsert onto an existing file**: the
new panoptic home is a long-lived instance DB that may already hold projects and
plugins. So it creates the file only when it is missing, refuses a file that is
still in the legacy shape (that is `migrate-home`'s job), and is idempotent --
registering the same folder twice is one row.

`panoptic_config.id` is the *instance* id and has nothing to do with any
project; `_init_config` generates one on first open, and so do we, so the file
is complete before the new panoptic ever sees it.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid

from ..errors import MigratorError
from ..home import TARGET_TABLES, map_plugin_type
from ..schema import PRAGMAS, checkpoint, create_db

#: `panoptic_db.DEFAULT_USER_ID`; every `tab_data.user_id` / `user_defaults.
#: user_id` in every project.db refers to it, across database files.
DEFAULT_USER_ID = "default"
DEFAULT_USER = (DEFAULT_USER_ID, "default", "default user", None)


class HomeDbError(MigratorError):
    """The panoptic home DB cannot be used as a registration target."""


def read_project_config(project_db):
    """`(id, name, description)` out of a migrated folder's `project.db`.

    The id is the load-bearing one: it is what `projects.id` must equal.
    """
    project_db = os.path.abspath(os.path.expanduser(project_db))
    if os.path.isdir(project_db):
        project_db = os.path.join(project_db, "project.db")
    if not os.path.isfile(project_db):
        raise HomeDbError(
            "%s has no project.db -- not a migrated project folder" % (
                os.path.dirname(project_db) or project_db))
    conn = sqlite3.connect("file:%s?mode=ro" % project_db, uri=True)
    try:
        rows = dict(conn.execute("SELECT key, value FROM project_config"))
    except sqlite3.DatabaseError as exc:
        raise HomeDbError("cannot read %s: %s" % (project_db, exc))
    finally:
        conn.close()

    def decode(key):
        raw = rows.get(key)
        if isinstance(raw, (str, bytes, bytearray)):
            try:
                return json.loads(raw)
            except ValueError:
                return raw
        return raw

    id_ = decode("id")
    if not id_:
        raise HomeDbError("%s has no project_config.id -- the new panoptic "
                          "cannot load a folder without one" % project_db)
    return str(id_), decode("name"), decode("description")


class PanopticHomeWriter:
    """Create-or-open a new-format panoptic.db and upsert rows into it."""

    def __init__(self, path, report=None):
        self.path = os.path.abspath(os.path.expanduser(path))
        self.report = report
        self.conn = None
        self.created = False
        self.notes = []
        self.stats = {"projects_registered": 0, "projects_updated": 0,
                      "plugins_registered": 0}

    # -- open / close ---------------------------------------------------
    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()

    def open(self):
        if os.path.exists(self.path):
            self._check_existing()
            self.conn = sqlite3.connect(self.path)
            for pragma in PRAGMAS:
                self.conn.execute(pragma)
        else:
            parent = os.path.dirname(self.path) or "."
            os.makedirs(parent, exist_ok=True)
            self.conn = create_db(self.path, "panoptic")
            self.created = True
        self._ensure_config()
        self._ensure_default_user()
        self.conn.commit()
        return self

    def _check_existing(self):
        conn = sqlite3.connect("file:%s?mode=ro" % self.path, uri=True)
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        except sqlite3.DatabaseError as exc:
            raise HomeDbError("%s exists but is not a sqlite database (%s)"
                              % (self.path, exc))
        finally:
            conn.close()
        if set(TARGET_TABLES) <= tables:
            return
        if "panoptic" in tables and "projects" in tables:
            raise HomeDbError(
                "%s is a *legacy* panoptic home (tables: panoptic, projects, "
                "plugins). Convert it first with `python -m migrator "
                "migrate-home %s --out <new panoptic.db>` -- this command never "
                "rewrites a legacy home in place." % (self.path, self.path))
        raise HomeDbError(
            "%s exists but is not a panoptic home DB (tables: %s)"
            % (self.path, ", ".join(sorted(tables)) or "(none)"))

    def close(self):
        if self.conn is not None:
            self.conn.commit()
            self.conn.close()
            self.conn = None
            checkpoint(self.path)

    # -- the two synthesised rows ---------------------------------------
    def _ensure_config(self):
        """`panoptic_config`: one row per struct field, JSON-encoded values.

        Mirrors `KeyValueSchema.ensure_keys` + `PanopticDB._init_config`: seed
        the three keys, then fill `id` with a UUID if it is still NULL.
        """
        for key in ("id", "name", "description"):
            self.conn.execute(
                "INSERT OR IGNORE INTO panoptic_config (key, value) "
                "VALUES (?, NULL)", (key,))
        row = self.conn.execute(
            "SELECT value FROM panoptic_config WHERE key='id'").fetchone()
        if row is None or row[0] is None:
            self.instance_id = str(uuid.uuid4())
            self.conn.execute(
                "UPDATE panoptic_config SET value=? WHERE key='id'",
                (json.dumps(self.instance_id),))
            self.notes.append("generated the panoptic instance id %s"
                              % self.instance_id)
        else:
            self.instance_id = _decode(row[0])

    def _ensure_default_user(self):
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO users (id, name, description, password_hash) "
            "VALUES (?,?,?,?)", DEFAULT_USER)
        if cur.rowcount:
            self.notes.append("created the default user %r" % DEFAULT_USER_ID)

    def set_instance_name(self, name=None, description=None):
        for key, value in (("name", name), ("description", description)):
            if value is not None:
                self.conn.execute(
                    "UPDATE panoptic_config SET value=? WHERE key=?",
                    (json.dumps(value), key))

    # -- registration ----------------------------------------------------
    def register_project(self, project_id, path, name=None,
                         excluded_plugins=()):
        """Upsert one project. `project_id` must come from its project.db."""
        path = os.path.abspath(os.path.expanduser(path))
        name = name or os.path.basename(path.rstrip(os.sep))
        excluded = json.dumps(list(excluded_plugins or []))

        clash = self.conn.execute(
            "SELECT id, path FROM projects WHERE path=? AND id<>?",
            (path, project_id)).fetchone()
        if clash:
            self.conn.execute("DELETE FROM projects WHERE id=?", (clash[0],))
            self.notes.append(
                "path %s was registered under a different id (%s); replaced it "
                "with %s, the id this folder's project.db actually holds"
                % (path, clash[0], project_id))

        existed = self.conn.execute(
            "SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone()
        self.conn.execute(
            "INSERT OR REPLACE INTO projects (id, path, name, excluded_plugins) "
            "VALUES (?,?,?,?)", (project_id, path, name, excluded))
        self.conn.commit()
        if existed:
            self.stats["projects_updated"] += 1
            return "updated"
        self.stats["projects_registered"] += 1
        return "registered"

    def register_project_folder(self, folder, name=None, excluded_plugins=()):
        """Register a migrated folder, reading the id out of its project.db."""
        project_id, config_name, _ = read_project_config(folder)
        action = self.register_project(
            project_id, folder, name or config_name, excluded_plugins)
        return project_id, action

    def register_plugin(self, name, install_path, source_type, source_path):
        source_type, warning = map_plugin_type(source_type)
        if warning:
            self.notes.append("%s: %s" % (name, warning))
        if not source_path:
            # NOT NULL upstream. For a `path` plugin the install dir *is* the
            # source, so reuse it rather than writing '' and breaking reinstall.
            source_path = install_path or ""
            if source_path:
                self.notes.append(
                    "%s had no source: using its install path %s as source_path"
                    % (name, source_path))
        self.conn.execute(
            "INSERT OR REPLACE INTO plugins "
            "(id, install_path, source_type, source_path) VALUES (?,?,?,?)",
            (name, install_path or "", source_type, source_path))
        self.conn.commit()
        self.stats["plugins_registered"] += 1
        return name

    # -- read back --------------------------------------------------------
    def projects(self):
        return list(self.conn.execute(
            "SELECT id, path, name, excluded_plugins FROM projects ORDER BY name"))

    def plugins(self):
        return list(self.conn.execute(
            "SELECT id, install_path, source_type, source_path FROM plugins "
            "ORDER BY id"))


def _decode(raw):
    if isinstance(raw, (str, bytes, bytearray)):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw
