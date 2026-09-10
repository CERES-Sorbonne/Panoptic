"""System properties and the `id_registry` seeds (analysis/ID_STRATEGY.md).

Two rules do all the work here:

1. **Every legacy id is preserved verbatim** -- `maps.data` embeds instance ids
   as an opaque JSON array, and every other cross-table reference becomes a
   plain column copy. Nothing is renumbered.
2. **`id_registry` counters are *next free*, not last used.** Seeding a key to
   `max(id)` re-issues the highest id and the target's `INSERT OR REPLACE`
   silently clobbers a migrated row. Seed `max(id) + 1`, and `1` (the struct
   default) when the table is empty -- `ir.max_ids()` returns `None` there.
   `max = 0` is *not* the empty case: `image_atlas` id 0 is real (v7c).

The nine system properties are allocated **above** the highest legacy property
id. Legacy property ids are dense from 1, so anything lower or interleaved
collides; and the target keys them on `system_key`, so writing them ourselves is
idempotent with `Project._ensure_system_properties()`.
"""

from __future__ import annotations

from collections import namedtuple

SystemProperty = namedtuple("SystemProperty", "key dtype mode")

#: verbatim from `data/system_properties.py::SYSTEM_PROPERTIES`, in declaration
#: order -- the order in which ids are handed out.
SYSTEM_PROPERTIES = (
    SystemProperty("id",         "id",     "id"),
    SystemProperty("sha1",       "sha1",   "sha1"),
    SystemProperty("file_id",    "number", "id"),
    SystemProperty("folder",     "folder", "sha1"),
    SystemProperty("name",       "text",   "file"),
    SystemProperty("format",     "text",   "sha1"),
    SystemProperty("width",      "number", "sha1"),
    SystemProperty("height",     "number", "sha1"),
    SystemProperty("created_at", "date",   "file"),
)

#: legacy virtual (never stored) computed property ids -> new system key.
#: `-3` (average hash) has no target: references to it are dropped (L1).
LEGACY_COMPUTED = {-1: "id", -2: "sha1", -3: None, -4: "folder",
                   -5: "width", -6: "height", -7: "name"}

#: the 11 `IdRegistry` fields, in struct order. All 11 must be written: a key we
#: omit is seeded to 1 by `ensure_keys()` and collides on first allocation, and
#: a NULL value makes `allocate()` raise TypeError.
ID_REGISTRY_KEYS = ("file_sources", "folders", "files", "instances",
                    "properties", "tags", "property_groups",
                    "vector_types", "image_types", "image_atlas", "maps")

#: which output DB holds the table each counter counts (for the post-conditions)
REGISTRY_TABLES = {
    "file_sources": ("data", "file_sources"), "folders": ("data", "folders"),
    "files": ("data", "files"), "instances": ("data", "instances"),
    "properties": ("data", "properties"), "tags": ("data", "tags"),
    "property_groups": ("data", "property_groups"),
    "vector_types": ("media", "vector_types"),
    "image_types": ("media", "image_types"),
    "image_atlas": ("media", "image_atlas"), "maps": ("media", "maps"),
}


def next_free(max_id):
    """`max + 1`, or the struct default `1` when there is nothing to count.

    `max_id` of 0 is a real maximum (atlas id 0), not "empty" -- hence the
    explicit `is None` test rather than a truthiness test.
    """
    return 1 if max_id is None else max_id + 1


class SystemPropertyPlan:
    """Ids for the nine system properties, allocated above the legacy max."""

    def __init__(self, max_legacy_property_id):
        self.base = next_free(max_legacy_property_id)
        self.ids = {sp.key: self.base + i
                    for i, sp in enumerate(SYSTEM_PROPERTIES)}
        self.next_property_id = self.base + len(SYSTEM_PROPERTIES)

    def rows(self):
        """(id, SystemProperty) pairs in declaration order."""
        return [(self.ids[sp.key], sp) for sp in SYSTEM_PROPERTIES]

    def remap_legacy_computed(self, legacy_id):
        """A stored negative property id -> the new system property id, or None.

        `None` means "drop the reference": either it is the average hash (-3,
        which has no target at all) or it is not a known computed id.
        """
        key = LEGACY_COMPUTED.get(legacy_id)
        return self.ids.get(key) if key else None
