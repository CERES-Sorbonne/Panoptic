"""Readers for the shapes that already have an `instances` table: v1 - v7c.

These eleven-minus-two shapes differ from the v7c target shape by exactly four
things a *reader* can see (`analysis/SCHEMA_MATRIX.md`, "Shape-to-shape delta"):

1. `properties.property_group_id` and the `property_group` table only exist
   from v5 -- a missing column simply reads as `None`;
2. `properties.type` may still say `'string'` before v4 -- normalised by
   `base.normalise_dtype`, which is `migrator/legacy/v4.py` in executable form;
3. `tags.parents` uses the `[0]` root sentinel before v3 -- normalised by
   `base.normalise_parents`;
4. `project` / `_project` / `ui_data` / `plugin_data` / `vectors` presence
   varies -- all handled table-by-table in `Reader`.

Everything else the upstream chain does is either a no-op for a reader (v3
rebuilds the table with identical columns, v6 adds indexes) or actively harmful
(v7 drops the vectors table). See `migrator/legacy/__init__.py`.

So one reader covers v1 through v6, and a second covers the three v7 variants;
they differ only in which optional tables are present, which is why `V7Reader`
is a thin subclass.
"""

from __future__ import annotations

from ..ir import Instance, Property
from .base import Reader, normalise_dtype


class ModernReader(Reader):
    """v1, v2, v3/v4, v5, v6 -- and, via the subclass, v7a/v7b/v7c."""

    shapes = ("v1", "v2", "v3_v4", "v5", "v6")

    def read_entities(self):
        self.read_folders()
        self.read_instances()
        self.read_property_groups()
        self.read_properties()
        self.read_tags()
        self.read_values()
        self.stat_instances()

    def read_instances(self):
        ahash = 0
        for r in self.rows("SELECT id, folder_id, name, extension, sha1, url, "
                           "width, height, ahash FROM instances"):
            if r["ahash"]:
                ahash += 1
            self.ir.instances.append(Instance(
                id=r["id"], folder_id=r["folder_id"], name=r["name"],
                extension=r["extension"], sha1=r["sha1"], url=r["url"],
                width=r["width"], height=r["height"]))
        self.ahash_count = ahash
        # `instances_old` is upstream v3_sql's leftover and is never dropped
        # (MAPPING U10). Ignore it -- it is a stale copy, not data.
        if self.has("instances_old"):
            self.warn("ignoring the stale `instances_old` table left behind by "
                      "the upstream v3 migration (MAPPING U10)")

    def read_properties(self):
        cols = self._columns("properties")
        has_group = "property_group_id" in cols   # v5+
        has_mode = "mode" in cols                 # P1+
        for r in self.rows("SELECT * FROM properties"):
            self.ir.properties.append(Property(
                id=r["id"], name=r["name"],
                dtype=normalise_dtype(r["type"]),
                mode=(r["mode"] or "id") if has_mode else "sha1",
                property_group_id=r["property_group_id"] if has_group else None))

    def read_values(self):
        props = self.property_index()
        for r in self.rows("SELECT property_id, instance_id, value "
                           "FROM instance_property_values"):
            prop = props.get(r["property_id"])
            if prop is None:
                self.warn("instance value for unknown property %r"
                          % (r["property_id"],))
                continue
            if prop.mode != "id":
                self.warn("property %d is mode=%r but has instance-scoped "
                          "values; routing by the declared mode"
                          % (prop.id, prop.mode))
            self.route_value(prop, r["instance_id"], r["value"], "instance")

        for r in self.rows("SELECT property_id, sha1, value "
                           "FROM image_property_values"):
            prop = props.get(r["property_id"])
            if prop is None:
                self.warn("sha1 value for unknown property %r"
                          % (r["property_id"],))
                continue
            if prop.mode != "sha1":
                self.warn("property %d is mode=%r but has sha1-scoped values; "
                          "routing by the declared mode" % (prop.id, prop.mode))
            self.route_value(prop, r["sha1"], r["value"], "sha1")


class V7Reader(ModernReader):
    """v7a, v7b, v7c -- the shape everything else is normalised *to*.

    Structurally identical to v6 as far as the IR is concerned. The three v7
    deltas are all in tables the IR either drops (`vectors` re-keyed on
    `vector_type`, `raw_images`) or reads generically (`_project` for v7b,
    `maps`/`atlas` for v7c).
    """

    shapes = ("v7a", "v7b", "v7c")
