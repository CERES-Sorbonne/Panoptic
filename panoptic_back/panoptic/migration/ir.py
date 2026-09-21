"""The intermediate representation (IR) every legacy reader produces.

Task 3.2. One reader per legacy schema shape fills this structure; tasks 3.3-3.5
consume it and know nothing about which of the 11 legacy shapes it came from.

Shape of the IR
---------------
The IR is the **normalised v7c shape**, not the target shape. Its field names are
the legacy ones (`instances`, `properties.dtype`, `instance_values`,
`sha1_values`, ...) because that is the vocabulary `analysis/MAPPING.md` is
written in: MAPPING maps *v7c* onto the four new databases, so handing the
writers a clean v7c keeps that document the single source of truth for the
conversion. The IR is therefore "v7c with every known quirk already fixed":

* `tags.parents` never contains the pre-v3 root sentinel `0`;
* `properties.dtype` is never `'string'` (the v4 rename is applied defensively
  to every shape, per `migrator/legacy/v4.py`);
* every instance has an id, a `folder_id` and a filesystem path in `url`
  (P0's folder-id-in-`paths` bug and the P0/P1 `/images/<abspath>` served-URL
  prefix are already undone);
* every property has a `mode` (P0, which has no such column, is all `'sha1'`);
* values are already split into instance-scoped and sha1-scoped lists
  (P0's single table and P1's `image_id = -1` sentinel are already resolved).

What is deliberately absent
---------------------------
Per the signed-off decisions in CLAUDE.md, the IR carries **no** tabs/UI blobs
and **no** `raw_images` payloads. It carries their *counts* in `Dropped`, so
every run report can state exactly what was discarded.

Vectors are the one conditional case (user decision, 2026-09-19): they are
**kept for the v7 shapes only** (v7a/v7b/v7c, whose `vector_type` rows record
the producing model) and dropped for everything older. Even when kept, the IR
does not hold the vector *payloads*: it holds the `vector_type` rows, the
expected byte length per type, and the path of the legacy DB, and the media
writer streams the rows straight from the (read-only) source. A project with
millions of 2 KB vectors must not be materialised in memory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------
# structural entities
# --------------------------------------------------------------------------

@dataclass
class Folder:
    id: int
    path: str
    name: str
    parent: Optional[int] = None


@dataclass
class Instance:
    """One legacy `instances` row. Becomes one `files` + one `instances` row."""

    id: int
    folder_id: int
    name: str            # already includes the extension, per MAPPING §3.3
    extension: str
    sha1: str
    url: str             # filesystem path, `/images/` prefix already stripped
    width: Optional[int] = None
    height: Optional[int] = None
    #: `'YYYY-MM-DD HH:MM:SS'` from the file's mtime, or None when it is gone.
    created_at: Optional[str] = None


# --------------------------------------------------------------------------
# logged entities
# --------------------------------------------------------------------------

@dataclass
class PropertyGroup:
    id: int
    name: str


@dataclass
class Property:
    id: int
    name: str
    dtype: str                       # legacy `type`, never 'string'
    mode: str                        # 'id' or 'sha1'
    property_group_id: Optional[int] = None

    @property
    def is_tag(self):
        """Value routing is on dtype FIRST, mode second (MAPPING §4.2)."""
        return self.dtype in ("tag", "multi_tags")


@dataclass
class Tag:
    id: int
    property_id: int                 # becomes tags.list_id in the target
    value: str
    parents: List[int] = field(default_factory=list)   # sentinel 0 removed
    color: Optional[int] = None


@dataclass
class Value:
    """A property value. `key` is an instance id or a sha1 depending on scope.

    `raw` is the legacy JSON *text*, copied verbatim into the target's value
    column; `value` is the same thing decoded, which is what the genesis
    `entity_log.changes` snapshot needs (MAPPING §6.3).
    """

    property_id: int
    key: Any                         # int instance_id, or str sha1
    raw: Optional[str]
    value: Any


# --------------------------------------------------------------------------
# media (thumbnails / atlas / maps) -- consumed by task 3.5
# --------------------------------------------------------------------------

@dataclass
class Thumbnail:
    sha1: str
    small: Optional[bytes] = None
    medium: Optional[bytes] = None
    large: Optional[bytes] = None


@dataclass
class AtlasSheet:
    id: int
    atlas_nb: int
    width: int
    height: int
    cell_width: int
    cell_height: int
    sha1_mapping: Optional[str] = None


@dataclass
class VectorType:
    """One legacy v7 `vector_type` row, already normalised for the target.

    `source` is the plugin name the vectors belong to (NULL -> 'unknown');
    `params` is the decoded dict (NULL / junk -> {}), which the target stores as
    `json.dumps(params)` in a `JSON NOT NULL` column.
    """

    id: int
    source: str
    params: Dict[str, Any]


@dataclass
class VectorSource:
    """Where the kept vectors are streamed from (MAPPING 7.2).

    `path` is the legacy project DB, opened read-only again by the writer.
    `rows` is the legacy `vectors` row count; `lengths` the expected `data`
    byte length per type id (the modal length, see `readers.base`). Rows that
    disagree are skipped and reported by the writer, never written.
    """

    path: str
    rows: int = 0
    lengths: Dict[int, int] = field(default_factory=dict)


@dataclass
class MapRow:
    id: int
    source: Optional[str]
    name: Optional[str]
    key: Optional[str]
    count: Optional[int]
    data: Optional[str]


# --------------------------------------------------------------------------
# what was thrown away
# --------------------------------------------------------------------------

@dataclass
class Dropped:
    """Counts only -- never payloads. See CLAUDE.md "Signed-off decisions"."""

    tabs: int = 0                    # L3
    ui_data_keys: List[str] = field(default_factory=list)   # L3
    #: v1-v6/P0/P1 (and v7 under --drop-vectors): recompute in the new Panoptic.
    #: Always 0 when the vectors were carried over -- see `vectors_kept`.
    vectors: int = 0
    vector_types: int = 0
    #: True when this run carried the v7 vectors over instead of dropping them
    vectors_kept: bool = False
    kept_vectors: int = 0            # legacy rows offered to the writer
    kept_vector_types: int = 0
    raw_images: int = 0              # L6
    raw_image_bytes: int = 0
    ahash: int = 0                   # L1
    #: v1 only, L8: no target concept at all, so it is dumped into the report
    #: rather than silently binned.
    action_params: Dict[str, Any] = field(default_factory=dict)
    default_vector: Optional[str] = None   # L9

    def to_json(self):
        return asdict(self)

    def summary_lines(self):
        """One line per thing this run threw away, with its real count.

        Every run must state what happened to the vectors out loud (MISSION
        3.5): dropped (v1-v6/P0/P1, the new Panoptic recomputes them, but only if
        the user knows to ask) or carried over (v7). Exactly one vector line is
        emitted, even when the count is 0, so its absence is never mistaken for
        "the migrator forgot to look".
        """
        if self.vectors_kept:
            lines = ["carried over: %d legacy vector(s) in %d vector type(s) "
                     "(v7 byte copy; any row failing validation is listed "
                     "separately as skipped)"
                     % (self.kept_vectors, self.kept_vector_types)]
        else:
            lines = ["dropped by design: %d vector(s) in %d vector type(s) -- "
                     "recompute them in the new Panoptic"
                     % (self.vectors, self.vector_types)]
        if self.default_vector:
            lines.append("dropped by design: default_vector=%r (L9: no target "
                         "concept)" % (self.default_vector,))
        if self.tabs or self.ui_data_keys:
            lines.append("dropped by design: %d tab(s) and all UI layout data "
                         "(L3)%s"
                         % (self.tabs,
                            "" if not self.ui_data_keys
                            else ", ui_data keys: " + ", ".join(self.ui_data_keys)))
        if self.raw_images:
            lines.append("dropped by design: %d raw_images blob(s), %d byte(s) "
                         "(L6) -- the originals stay on disk"
                         % (self.raw_images, self.raw_image_bytes))
        if self.ahash:
            lines.append("dropped by design: %d ahash value(s) (L1)" % self.ahash)
        if self.action_params:
            lines.append("dropped by design: action_params has no target "
                         "concept (L8); recorded verbatim in the report: %s"
                         % ", ".join(sorted(self.action_params)))
        return lines


# --------------------------------------------------------------------------
# the whole thing
# --------------------------------------------------------------------------

@dataclass
class ProjectIR:
    shape: str                       # the sniffed source shape, for the report
    variant: str = ""

    folders: List[Folder] = field(default_factory=list)
    instances: List[Instance] = field(default_factory=list)
    property_groups: List[PropertyGroup] = field(default_factory=list)
    properties: List[Property] = field(default_factory=list)
    tags: List[Tag] = field(default_factory=list)

    #: non-tag values, keyed by instance id / sha1
    instance_values: List[Value] = field(default_factory=list)
    sha1_values: List[Value] = field(default_factory=list)
    #: tag dtypes, already exploded one row per tag id (MAPPING §4.2)
    instance_tag_values: List[tuple] = field(default_factory=list)  # (instance_id, property_id, tag_id)
    sha1_tag_values: List[tuple] = field(default_factory=list)      # (sha1, property_id, tag_id)

    #: legacy `project` kv, decoded. Empty for P0/P1/v1/v2 and for v7b.
    project_params: Dict[str, Any] = field(default_factory=dict)
    #: plugin name -> params dict (from `plugin_data` / v1 `plugin_defaults`)
    plugin_params: Dict[str, Any] = field(default_factory=dict)
    #: `plugin_data` keys with no addressable owner (MAPPING §8.3)
    orphan_plugin_data: Dict[str, Any] = field(default_factory=dict)

    thumbnails: List[Thumbnail] = field(default_factory=list)
    atlas: List[AtlasSheet] = field(default_factory=list)
    maps: List[MapRow] = field(default_factory=list)

    #: v7 only (empty otherwise): the kept `vector_type` rows, and where the
    #: vector payloads are streamed from. `vector_source` is None whenever the
    #: vectors are dropped.
    vector_types: List[VectorType] = field(default_factory=list)
    vector_source: Optional[VectorSource] = None

    dropped: Dropped = field(default_factory=Dropped)
    warnings: List[str] = field(default_factory=list)

    # -- derived ----------------------------------------------------------
    def max_ids(self):
        """`max(id)` per entity, for seeding `id_registry` (analysis/ID_STRATEGY.md).

        Returns *max*, not *next free* -- the +1 is the writer's job, and it
        must also handle the empty case (max is None here).
        """
        def _max(rows, attr="id"):
            vals = [getattr(r, attr) for r in rows]
            return max(vals) if vals else None

        return {
            "folders": _max(self.folders),
            "files": _max(self.instances),
            "instances": _max(self.instances),
            "properties": _max(self.properties),
            "property_groups": _max(self.property_groups),
            "tags": _max(self.tags),
            "image_atlas": _max(self.atlas),
            "maps": _max(self.maps),
            "vector_types": _max(self.vector_types),
        }

    def counts(self):
        return {
            "folders": len(self.folders),
            "instances": len(self.instances),
            "properties": len(self.properties),
            "property_groups": len(self.property_groups),
            "tags": len(self.tags),
            "instance_values": len(self.instance_values),
            "sha1_values": len(self.sha1_values),
            "instance_tag_values": len(self.instance_tag_values),
            "sha1_tag_values": len(self.sha1_tag_values),
            "thumbnails": len(self.thumbnails),
            "atlas": len(self.atlas),
            "maps": len(self.maps),
            "vector_types": len(self.vector_types),
            "vectors": self.vector_source.rows if self.vector_source else 0,
            "project_params": len(self.project_params),
            "plugin_params": len(self.plugin_params),
        }

    def to_json(self):
        return {
            "shape": self.shape,
            "variant": self.variant,
            "counts": self.counts(),
            "max_ids": self.max_ids(),
            "dropped": self.dropped.to_json(),
            "warnings": list(self.warnings),
        }

    def summary(self):
        c = self.counts()
        return ("%s: %d folders, %d instances, %d properties, %d tags, "
                "%d+%d values, %d+%d tag assignments"
                % (self.shape, c["folders"], c["instances"], c["properties"],
                   c["tags"], c["instance_values"], c["sha1_values"],
                   c["instance_tag_values"], c["sha1_tag_values"]))


def dumps(obj):
    """`json.dumps` with the target's compact separators (MAPPING §6.2)."""
    return json.dumps(obj, separators=(",", ":"))
