"""Bespoke readers for the two pre-versioned eras, P0 (0.0.x) and P1 (0.1-0.2.x).

**No upstream migration path exists for these.** The `migrations/v*.py` chain
starts at v3 and its earliest script (`v3_sql`) assumes an `instances` table
that neither era has, so both readers are written from the schema up. The one
reference point is `panoptic_back/panoptic/scripts/convert_old_db.py` on `main`
-- a commented-out one-off script for a single user's P1 database. Two of its
details are load-bearing and are reproduced here: `row[5] = row[5][8:]` (strip
the `/images/` served-URL prefix) and `if row[1] == -1` (the sha1-scoped
sentinel in `property_values`).
"""

from __future__ import annotations

from ..ir import Instance, Property
from .base import Reader, json_loads, normalise_dtype, strip_served_url


class P0Reader(Reader):
    """0.0.x: `images` keyed by **sha1**, values in `images_properties`.

    Three things make P0 unlike every later shape:

    * **There is no instance identity** (MAPPING U5/L7). `images` has a sha1
      primary key, so two copies of one file on disk were one row. We invent
      one instance per sha1, numbered from 1 in stable `rowid` order.
    * **`images.paths` holds a folder id, not a path** (MAPPING U6) -- a 0.0.8
      bug, and since `images` has no `folder_id` column it is the *only*
      file->folder link there is.
    * **`properties` has no `mode` column** (MAPPING U7). Every value is
      sha1-keyed, so every P0 property is `mode='sha1'`.
    """

    shapes = ("P0",)

    def read_entities(self):
        self.read_folders()
        self.read_instances()
        self.read_properties()
        self.read_tags()
        self.read_values()
        self.stat_instances()

    def read_instances(self):
        folder_ids = {f.id for f in self.ir.folders}
        default_folder = min(folder_ids) if folder_ids else None
        ahash = 0
        no_folder = 0
        for next_id, r in enumerate(
                self.rows("SELECT sha1, height, width, name, extension, paths, "
                          "url, ahash FROM images ORDER BY rowid"), start=1):
            if r["ahash"]:
                ahash += 1
            paths = json_loads(r["paths"], [])
            folder_id = None
            if isinstance(paths, list) and paths:
                try:
                    folder_id = int(paths[0])
                except (TypeError, ValueError):
                    folder_id = None
            if folder_id not in folder_ids:
                folder_id = default_folder
                no_folder += 1
            self.ir.instances.append(Instance(
                id=next_id, folder_id=folder_id, name=r["name"],
                extension=r["extension"], sha1=r["sha1"],
                url=strip_served_url(r["url"]),
                width=r["width"], height=r["height"]))
        self.ahash_count = ahash
        if no_folder:
            self.warn("%d P0 image(s) had no usable folder id in `images.paths` "
                      "(the 0.0.8 bug, MAPPING U6); assigned folder %r"
                      % (no_folder, default_folder))
        self.warn("P0 stores no per-copy instance identity: %d instances were "
                  "invented, one per sha1. Duplicate files on disk collapse "
                  "into one (L7); re-import the folder afterwards to recover "
                  "them." % len(self.ir.instances))

    def read_properties(self):
        for r in self.rows("SELECT id, name, type FROM properties"):
            self.ir.properties.append(Property(
                id=r["id"], name=r["name"],
                dtype=normalise_dtype(r["type"]),
                mode="sha1"))          # P0 has no `mode` column at all

    def read_values(self):
        props = self.property_index()
        for r in self.rows("SELECT sha1, property_id, value FROM images_properties"):
            prop = props.get(r["property_id"])
            if prop is None:
                self.warn("value for unknown property %r" % (r["property_id"],))
                continue
            self.route_value(prop, r["sha1"], r["value"], "sha1")

    def record_drops(self):
        super().record_drops()
        # P0 keeps the vector inline on `images`; there is no `vectors` table
        # for the base class to count.
        self.ir.dropped.vectors = int(self.scalar(
            "SELECT COUNT(*) FROM images WHERE vector IS NOT NULL", default=0))


class P1Reader(Reader):
    """0.1.x-0.2.x: id-keyed `images`, one unified `property_values` table.

    P1 already has instance identity (`images.id`), so the promotion to the v7c
    shape is a rename. The two quirks are the `/images/<abspath>` url prefix and
    the `image_id = -1` / `sha1 = ''` sentinel pair that packs both value scopes
    into one table (MAPPING U8).
    """

    shapes = ("P1",)

    #: `property_values.image_id` when the row is sha1-scoped, not instance-scoped.
    SHA1_SCOPED = -1

    def read_entities(self):
        self.read_folders()
        self.read_instances()
        self.read_properties()
        self.read_tags()
        self.read_values()
        self.stat_instances()

    def read_instances(self):
        for r in self.rows("SELECT id, folder_id, name, extension, sha1, url, "
                           "height, width FROM images"):
            self.ir.instances.append(Instance(
                id=r["id"], folder_id=r["folder_id"], name=r["name"],
                extension=r["extension"], sha1=r["sha1"],
                url=strip_served_url(r["url"]),
                width=r["width"], height=r["height"]))
        # P1 moved ahash out to `computed_values`; it is dropped either way (L1),
        # so it is only counted.
        self.ahash_count = int(self.scalar(
            "SELECT COUNT(*) FROM computed_values WHERE ahash IS NOT NULL "
            "AND ahash != ''", default=0)) if self.has("computed_values") else 0

    def read_properties(self):
        for r in self.rows("SELECT id, name, type, mode FROM properties"):
            self.ir.properties.append(Property(
                id=r["id"], name=r["name"],
                dtype=normalise_dtype(r["type"]),
                mode=r["mode"] or "id"))

    def read_values(self):
        props = self.property_index()
        for r in self.rows("SELECT property_id, image_id, sha1, value "
                           "FROM property_values"):
            prop = props.get(r["property_id"])
            if prop is None:
                self.warn("value for unknown property %r" % (r["property_id"],))
                continue
            if r["image_id"] == self.SHA1_SCOPED:
                self.route_value(prop, r["sha1"], r["value"], "sha1")
            else:
                self.route_value(prop, r["image_id"], r["value"], "instance")

    def record_drops(self):
        super().record_drops()
        if self.has("computed_values"):
            self.ir.dropped.vectors = int(self.scalar(
                "SELECT COUNT(*) FROM computed_values WHERE vector IS NOT NULL",
                default=0))
