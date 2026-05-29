# InstanceTagValue / Sha1TagValue Refactor

## Goal
Replace JSON blob storage for `tag` and `multi_tags` properties with explicit junction tables
(`instance_tag_values`, `sha1_tag_values`) that have one row per key/tag connection.
This enables fast SQL counts without loading and parsing all values in Python.

## Key Design Decisions
- `UpsertCommit` format **stays unchanged** — callers still send `value=[3,7,12]` in `InstanceValue`/`Sha1Value`
- The writer internally explodes the list into individual `InstanceTagValue` rows
- `InstanceValue`/`Sha1Value` tables **no longer store tag/multi-tag rows** — the junction tables are the new truth
- Both `tag` and `multi_tag` dtypes use the new architecture
- Count operations are a **separate reader API**, not part of the normal delta/sync flow
- Junction tables are **trackable** (have `commit_id`, `operation`, `sequence`) to support `re_compute` on commit toggle
- `FileValue` does **not** get a junction table — no tag annotation needed for file-mode values

## Resolved Design Questions

- **Migration**: Ignore for now — no `_migrate_v3_to_v4` needed at this stage
- **Delta response**: Merge junction table results into existing `instance_values`/`image_values` keys as reconstructed lists — purely a backend structural change, frontend unchanged
- **Reader API**: Reader looks up the property dtype internally (option C) — no `is_multi_tag` param on `get_values_for_instances` / `get_full_column`, minimal cost, always correct
- **OP_DIFF**: Remove entirely — never used by any caller, no longer meaningful with row-per-tag storage
- **`set_commit_active` re_compute**: Replay `instance_tag_values`/`sha1_tag_values` logs directly like any other trackable entity — `operation` field (OP_CREATE / OP_DELETE) is the flag for whether a connection is active. No merge value logic needed.

---

## Checklist

### models.py
- [ ] Add `InstanceTagValue(instance_id, property_id, tag_id)` — trackable
- [ ] Add `Sha1TagValue(sha1, property_id, tag_id)` — trackable
- [ ] `UpsertCommit` stays unchanged (no new fields)

### create.py
- [ ] Add `INSTANCE_TAG_VALUES_SCHEMA = EntitySchema(InstanceTagValue, table="instance_tag_values")`
- [ ] Add `SHA1_TAG_VALUES_SCHEMA = EntitySchema(Sha1TagValue, table="sha1_tag_values")`
- [ ] Add both to `ALL_SCHEMAS`
- [ ] Bump `datastore_desc` version to 4 (no migration function needed yet)

### entity_schema.py
- [ ] Remove `OP_DIFF` constant and `_apply_diff` function
- [ ] Remove multi-tag accumulation branch from `PropertyValueSchema.merge_logs`
- [ ] Remove `multi_tags_property_ids` param from `PropertyValueSchema.re_compute`

### data_writer.py
- [ ] `_upsert_commit_instance_values`: skip `tag` and `multi_tags` dtype properties (don't write blob)
- [ ] `_upsert_commit_sha1_values`: same
- [ ] Add `_upsert_commit_instance_tag_values(tx, data, commit_id, sequence)`: explode `value` list → individual `InstanceTagValue` rows with `OP_CREATE`, standard upsert+log
- [ ] Add `_upsert_commit_sha1_tag_values`: same
- [ ] `apply_upsert_commit`: call both new methods
- [ ] `set_commit_active` → add `re_compute` calls for both new schemas (plain `EntitySchema.re_compute`, no special merge)

### data_reader.py
- [ ] `get_values_for_instances`: detect tag/multi-tag by looking up property dtype; query `instance_tag_values`, group by `instance_id` → `{inst_id: [tag_ids]}`; return merged into same dict shape as before
- [ ] `get_full_column`: same dtype-lookup approach for tag properties
- [ ] `get_delta`: reconstruct tag lists from junction tables and return under existing `instance_values`/`image_values` keys
- [ ] Add `count_instances_per_tag(property_id=None) -> dict[int, int]`
- [ ] Add `count_sha1s_per_tag(property_id=None) -> dict[int, int]`

### No changes needed
- `commit.py` (CommitBuilder) — UpsertCommit format unchanged
- `routes/project_routes.py` — value writes unchanged
- `importer.py` — unchanged
- `plugin_interface.py` — unchanged
