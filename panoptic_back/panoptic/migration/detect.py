"""Source shape detection.

The recorded `panoptic.db_version` key LIES (see analysis/DBVERSION_MAP.md):
broken 0.4.x upgrade paths stamped `4` onto v1/v2 databases, and three mutually
incompatible schemas all report `7`. So detection is driven by `sqlite_master`
only; the recorded key is read purely as a cross-check and produces a warning
when it disagrees.

The 10 branches implement the sniffing rule published in
analysis/SCHEMA_MATRIX.md ("Shape sniffing rules (for task 3.1)").

Note: v3 and v4 are byte-identical schemas -- they CANNOT be told apart by
sniffing. They are one branch, `v3_v4`; a data heuristic (`properties.type =
'string'` only ever exists pre-v4) yields a non-authoritative `variant` hint,
and later stages must apply the v4 SQL defensively for the whole branch.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field

from .errors import SourceNotFound, UnknownShape

#: shape -> the db_version value a *healthy* project of that shape records.
#: None means the pre-versioned era (no `panoptic` table at all).
EXPECTED_DB_VERSION = {
    "P0": None,
    "P1": None,
    "v1": 1,
    "v2": 2,
    "v3_v4": (3, 4),
    "v5": 5,
    "v6": 6,
    "v7a": 7,
    "v7b": 7,
    "v7c": 7,
}

#: Human blurb per shape, used in the report and in --dry-run output.
SHAPE_NOTES = {
    "P0": "pre-versioned (0.0.x): sha1-keyed `images` + `images_properties`",
    "P1": "pre-versioned (0.1.x-0.2.x): id-keyed `images` + unified `property_values`",
    "v1": "0.3.0-0.3.3: first `instances` shape, tabs/plugin_defaults/action_params",
    "v2": "0.3.4-0.3.5rc4: ui_data + plugin_data kv tables",
    "v3_v4": "0.3.5rc5-0.4.5: thumbnail `images` + `project` kv "
             "(v3 and v4 are schema-identical; v4 SQL applied defensively)",
    "v5": "0.5.0-0.5.1: id_counter, property_group, properties.property_group_id",
    "v6": "0.5.2-0.6.3: v5 plus three indexes",
    "v7a": "0.6.4-0.6.8 / 0.7.1-0.7.4: vector_type, re-keyed vectors, raw_images",
    "v7b": "0.7.0: v7a with `project` misnamed `_project` (always empty)",
    "v7c": "0.7.5-0.7.6: v7a plus `maps` and `atlas`",
}


@dataclass
class SchemaFacts:
    """Everything detection is allowed to look at, captured from the source."""

    tables: set = field(default_factory=set)
    indexes: set = field(default_factory=set)
    image_columns: set = field(default_factory=set)
    has_string_property_type: bool = False
    recorded_db_version: object = None  # int, or None when absent/unparsable

    def to_json(self):
        return {
            "tables": sorted(self.tables),
            "indexes": sorted(self.indexes),
            "image_columns": sorted(self.image_columns),
            "has_string_property_type": self.has_string_property_type,
            "recorded_db_version": self.recorded_db_version,
        }


@dataclass
class Detection:
    shape: str
    variant: str          # same as shape, except "v3"/"v4" hint inside v3_v4
    facts: SchemaFacts
    warnings: list = field(default_factory=list)

    @property
    def note(self):
        return SHAPE_NOTES[self.shape]

    def to_json(self):
        return {
            "shape": self.shape,
            "variant": self.variant,
            "note": self.note,
            "recorded_db_version": self.facts.recorded_db_version,
            "warnings": list(self.warnings),
            "facts": self.facts.to_json(),
        }


def open_readonly(db_path):
    """Open a sqlite DB strictly read-only. The source is NEVER written to."""
    uri = "file:" + os.path.abspath(db_path).replace("?", "%3f").replace("#", "%23")
    conn = sqlite3.connect(uri + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def collect_facts(conn):
    """Read sqlite_master (+ the one data probe rule 8 needs) from a source DB."""
    facts = SchemaFacts()
    for row in conn.execute("SELECT type, name FROM sqlite_master"):
        if row["type"] == "table":
            facts.tables.add(row["name"])
        elif row["type"] == "index":
            facts.indexes.add(row["name"])

    if "images" in facts.tables:
        facts.image_columns = {
            r["name"] for r in conn.execute("PRAGMA table_info(images)")
        }

    if "properties" in facts.tables:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(properties)")}
        if "type" in cols:
            row = conn.execute(
                "SELECT 1 FROM properties WHERE type = 'string' LIMIT 1"
            ).fetchone()
            facts.has_string_property_type = row is not None

    if "panoptic" in facts.tables:
        row = conn.execute(
            "SELECT value FROM panoptic WHERE key = 'db_version'"
        ).fetchone()
        if row is not None:
            try:
                facts.recorded_db_version = int(str(row["value"]).strip().strip('"'))
            except (TypeError, ValueError):
                facts.recorded_db_version = row["value"]
    return facts


def sniff(facts):
    """Pure schema -> shape. Raises UnknownShape when nothing matches.

    Branch order is exactly the published rule; do not reorder.
    """
    t = facts.tables

    # 1-2: the two pre-versioned eras, identified by their own value tables.
    if "images_properties" in t:
        return "P0", "P0"
    if "property_values" in t:
        return "P1", "P1"

    # 3: from v1 on, `instances` is mandatory. No instances => not a legacy
    #    panoptic project DB we know how to read.
    if "instances" not in t:
        raise UnknownShape(
            "no `instances` table and no pre-versioned value table "
            "(`images_properties`/`property_values`) -- this does not look like a "
            "legacy panoptic project database. Tables found: "
            + (", ".join(sorted(t)) or "<none>")
        )

    # 4-6: the three v7 shapes, which all record db_version = 7.
    if "maps" in t or "atlas" in t:
        return "v7c", "v7c"
    if "_project" in t:
        return "v7b", "v7b"
    if "vector_type" in t:
        return "v7a", "v7a"

    # 7: v5/v6 differ by indexes only.
    if "id_counter" in t or "property_group" in t:
        return ("v6", "v6") if "idx_vectors_sha1" in facts.indexes else ("v5", "v5")

    # 8: v3 and v4 are schema-identical -- one branch, data-only hint.
    thumbnail_images = "images" in t and "small" in facts.image_columns
    if "project" in t or thumbnail_images:
        return "v3_v4", ("v3" if facts.has_string_property_type else "v4")

    # 9-10
    if "ui_data" in t or "plugin_data" in t:
        return "v2", "v2"
    if "tabs" in t:
        return "v1", "v1"

    raise UnknownShape(
        "an `instances` table is present but no shape marker matched "
        "(expected one of tabs / ui_data / project / id_counter / vector_type / "
        "_project / maps). Tables found: " + ", ".join(sorted(t))
    )


def _version_mismatch_warning(shape, recorded):
    expected = EXPECTED_DB_VERSION[shape]
    if expected is None:
        if recorded is not None:
            return ("sniffed shape %s is pre-versioned but the DB records "
                    "db_version=%r" % (shape, recorded))
        return None
    allowed = expected if isinstance(expected, tuple) else (expected,)
    if recorded is None:
        return ("sniffed shape %s should record db_version=%s but the key is "
                "absent" % (shape, "/".join(map(str, allowed))))
    if recorded not in allowed:
        return ("recorded db_version=%r disagrees with sniffed shape %s "
                "(expected %s) -- trusting the schema, not the key (known "
                "0.4.x upgrade bug)"
                % (recorded, shape, "/".join(map(str, allowed))))
    return None


def detect_db(db_path):
    """Detect the shape of a legacy project `panoptic.db`, read-only."""
    if not os.path.isfile(db_path):
        raise SourceNotFound("no such file: %s" % db_path)
    try:
        conn = open_readonly(db_path)
    except sqlite3.Error as exc:
        raise SourceNotFound("cannot open %s read-only: %s" % (db_path, exc))
    try:
        try:
            facts = collect_facts(conn)
        except sqlite3.DatabaseError as exc:
            raise SourceNotFound("%s is not a readable sqlite database: %s"
                                 % (db_path, exc))
    finally:
        conn.close()

    shape, variant = sniff(facts)
    warnings = []
    warn = _version_mismatch_warning(shape, facts.recorded_db_version)
    if warn:
        warnings.append(warn)
    if shape == "v3_v4":
        warnings.append(
            "v3 and v4 are schema-identical; data heuristic says %s. The v4 "
            "conversion is applied defensively either way." % variant
        )
    return Detection(shape=shape, variant=variant, facts=facts, warnings=warnings)
