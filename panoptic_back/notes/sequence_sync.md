# Plan: Sequence-based selective UI sync

## Problem

The UI currently has no incremental sync mechanism:
- Initial load streams everything from scratch via `GET /db_state_stream`
- `DbWatcher` detects new commits and emits `'commits'` socket event with commit IDs
- The frontend handler is registered under `'commit'` (wrong name) and receives no actual data — **the frontend never processes DB changes after initial load**

## Key data already in place

- Every write transaction increments a global `sequence` counter in the `sequence` table
- Every entity row (instances, properties, tags, values, …) gets `sequence` stamped on it
- `EntitySchema.get_since(tx, sequence)` returns all rows where `sequence > ?` (already implemented)
- Deleted rows are NOT physically removed — `_delete_function` marks `operation = OP_DELETE` and upserts the row back. So `get_since` covers both upserts and deletes
- `DataReader.get_max_sequence()` already exists

## Architecture

```
Write → sequence N stamped on every changed row
                │
         DbWatcher polls get_max_sequence()
                │  change detected
         emits 'db_update' {project_id, sequence: N}
                │
         Frontend receives 'db_update'
                │
         GET /delta?since=lastSequence
                │
         Backend reads all schemas get_since(lastSequence)
         separates upserts vs OP_DELETE rows
         returns StreamResult {sequence, chunk, instanceValues, imageValues, fileValues}
                │
         applyDelta() → reuses applyCommit + importXxxValuesArray
         lastSequence = delta.sequence
```

## Resolved design questions

### Q1 — When to capture `max_sequence` in the stream (B1 fix)

Capture `start_sequence = reader.get_max_sequence()` as the **first thing** in `_generate()`, **before** any entity reads.

Rationale: a write happening concurrently during the stream (between reads) may or may not land in the streamed data. Using `start_sequence` means the first delta call may return duplicate rows, but the frontend import functions are idempotent so duplicates are harmless. Using `end_sequence` risks silently missing data.

Pass `start_sequence` through to the **final** `LoadState.max_sequence` (the frontend only reads it after `isFinished`).

### Q2 — Optimal delta wire format (B6 fix)

Use `StreamResult` as the delta response type — same shape the stream already uses. This means:
- Zero new frontend parsing code
- `StreamChunk` gains optional `empty_*` fields (all default to `None`/omitted via `omit_defaults=True`)
- Backend encodes via `msgspec.json.encode(result)` — fastest Python JSON encoder
- Single HTTP response (not ndjson streaming), returned as `Response(content=..., media_type='application/json')`
- `LoadState.max_sequence` carries the new sequence to update `lastSequence`
- Columnar `InstanceValuesColumn` / `ImageValuesColumn` / `FileValuesColumn` used for value upserts (same as stream)
- Deleted values use new `empty_instance_values / empty_image_values / empty_file_values` fields in `StreamChunk` as lists of `[property_id, instance_id/sha1/file_id]` pairs

### Q3 — Apply order in `applyDelta`

Apply **chunk first** (imports instances, properties, tags into store), **then** columnar values. This ensures instances exist when their values arrive. Current plan had it backwards.

### Q4 — Concurrent `db_update` events

Use an `isSyncing = ref(false)` guard in the frontend. If a `db_update` arrives while a delta fetch is already in-flight, **skip it** — the in-flight request will already return the latest `max_sequence`, so the next real change will trigger a fresh delta that catches up. No queue needed.

### Q5 — Property groups (`tag_lists`) in delta

The stream currently sends `property_groups=[]` (not implemented). Delta does the same: skip `TAG_LISTS_SCHEMA`. When property groups are wired up in the stream, add them to the delta at the same time.

### Q6 — Folders in delta

Folders are loaded separately via `apiGetFolders()` in `dataStore.init()`, not via the stream. New folders created by import tasks will be missed by the delta unless explicitly included.

**Decision**: include `FOLDERS_SCHEMA.get_since(since)` in the delta. Add upserted folders as `chunk.folders` in `StreamChunk`, and deleted folders as `chunk.empty_folders`. Frontend `applyCommit` does not currently handle `folders` — this will need a new branch that calls `importFolders` incrementally (add/update entries without replacing the whole index).

**Open sub-question**: Does `applyCommit` need an incremental folder update, or can we trigger a full `apiGetFolders()` reload on any folder delta? A full reload is simpler but wasteful for large folder trees. Defer decision: start with full reload on folder change detection, optimize later.

## Step-by-step implementation

### B1 — `stream_models.py`: add `max_sequence` to `LoadState` + `empty_*` to `StreamChunk`

```python
class LoadState(msgspec.Struct):
    ...
    max_sequence: int = 0   # sequence captured at start of load

class StreamChunk(msgspec.Struct, omit_defaults=True):
    instances:        Optional[list[FullInstance]]  = None
    properties:       Optional[list[Any]]           = None
    tags:             Optional[list[Any]]            = None
    property_groups:  Optional[list[Any]]            = None
    # new delete fields:
    empty_instances:       Optional[list[int]]  = None
    empty_properties:      Optional[list[int]]  = None
    empty_tags:            Optional[list[int]]  = None
    empty_instance_values: Optional[list[list]] = None  # [[prop_id, inst_id], ...]
    empty_image_values:    Optional[list[list]] = None  # [[prop_id, sha1], ...]
    empty_file_values:     Optional[list[list]] = None  # [[prop_id, file_id], ...]
```

### B2 — `project_routes.py` (stream endpoint): capture `start_sequence`

```python
def _generate():
    with project._data_reader() as seq_reader:
        start_sequence = seq_reader.get_max_sequence()   # ← FIRST, before reads

    files           = project.get_files()
    properties      = project.get_properties()
    ...

    # In the final LoadState:
    state=LoadState(
        ...all finished flags and counters...,
        max_sequence=start_sequence,
    )
```

### B3 — `db_watcher.py`: track sequence not commit_id

```python
async def run(self):
    with DataReader(str(self._data_db_path)) as reader:
        self._last_seq = reader.get_max_sequence()   # was get_max_commit_id()
        while self._running:
            await asyncio.sleep(0.1)
            await self._check(reader)

async def _check(self, reader):
    new_seq = reader.get_max_sequence()
    if new_seq <= self._last_seq:
        return
    self._last_seq = new_seq
    await self._broadcast_fn(self._project_id, new_seq)
```

Broadcast signature: `Callable[[str, int], Coroutine]` (project_id, new_sequence).

### B4 — `panoptic_server.py`: emit `'db_update'`

```python
async def _broadcast_update(self, id_: str, sequence: int) -> None:
    sids = self._get_project_sids(id_)
    if not sids:
        return
    await self._sio.emit('db_update', {'project_id': id_, 'sequence': sequence}, to=sids)
```

Update `_attach_watcher` to pass `self._broadcast_update`.

### B5 — `data_reader.py`: add `get_delta(since)`

`sequence` is a DB-only column, not exposed on structs. To find the highest sequence
actually returned, run a cheap `MAX(sequence) WHERE sequence > ?` query per table
after the entity reads. This avoids the race where `get_max_sequence()` returns a
value higher than any row we're sending back, which would cause the frontend to
permanently skip those rows.

```python
def get_delta(self, since: int) -> dict:
    tables_with_seq = ['instances', 'files', 'folders', 'properties', 'tags',
                       'instance_values', 'sha1_values', 'file_values']
    data = {
        'instances':       INSTANCES_SCHEMA.get_since(self.conn, since),
        'files':           FILES_SCHEMA.get_since(self.conn, since),
        'folders':         FOLDERS_SCHEMA.get_since(self.conn, since),
        'properties':      PROPERTIES_SCHEMA.get_since(self.conn, since),
        'tags':            TAGS_SCHEMA.get_since(self.conn, since),
        'instance_values': INSTANCE_VALUES_SCHEMA.get_since(self.conn, since),
        'image_values':    SHA1_VALUES_SCHEMA.get_since(self.conn, since),
        'file_values':     FILE_VALUES_SCHEMA.get_since(self.conn, since),
    }
    # Compute max sequence of the rows we're actually returning, not the global max.
    max_seq = since
    for table in tables_with_seq:
        row = self.conn.execute(
            f"SELECT MAX(sequence) FROM {table} WHERE sequence > ?", (since,)
        ).fetchone()
        if row and row[0] is not None:
            max_seq = max(max_seq, row[0])
    data['sequence'] = max_seq
    return data
```

Frontend only advances `lastSequence` if `delta.state.maxSequence > lastSequence`.

### B6 — `project_routes.py`: new `GET /delta` endpoint

```python
@project_router.get('/delta')
def get_delta(since: int, project: Project2 = Depends(_dep)):
    with project._data_reader() as reader:
        raw = reader.get_delta(since)

    sequence = raw['sequence']
    file_map = {f.id: f for f in raw['files']}

    # Split each entity list into upserts (operation != OP_DELETE) and deletes
    # Build FullInstances for upserted instances (join with file_map)
    # Build columnar InstanceValuesColumn / ImageValuesColumn / FileValuesColumn for upserted values
    # Build empty_* lists from deleted rows (PKs only)

    result = StreamResult(
        state=LoadState(max_sequence=sequence, ...all finished flags=True...),
        chunk=StreamChunk(
            instances=[...],       # upserted FullInstances
            properties=[...],
            tags=[...],
            empty_instances=[...],
            empty_properties=[...],
            empty_tags=[...],
            empty_instance_values=[[prop_id, inst_id], ...],
            empty_image_values=[[prop_id, sha1], ...],
            empty_file_values=[[prop_id, file_id], ...],
        ),
        instance_values=[...],     # columnar InstanceValuesColumn
        image_values=[...],
        file_values=[...],
    )
    return Response(content=msgspec.json.encode(result), media_type='application/json')
```

For folders: if `raw['folders']` is non-empty, trigger a full `apiGetFolders` reload on the frontend (via a flag in `StreamChunk` or a separate field). Simple for now.

### F1 — `models.ts`: update `LoadState`, `DbCommit`, add `DeltaResult`

```ts
// LoadState: add
maxSequence: number

// DbCommit: empty_* fields are already there except for file values
// (already added in file property mode work)

// New:
export interface DeltaResult extends LoadResult {
    sequence: number
}
// LoadResult already has: chunk?, instanceValues?, imageValues?, fileValues?, state
// DeltaResult reuses the same shape — applyDelta just reads the same fields
```

### F2 — `dataStore.ts`: `lastSequence`, `applyDelta`

```ts
const lastSequence = ref<number>(0)

// In init(), when isFinished:
lastSequence.value = v.state.maxSequence ?? 0

// New:
function applyDelta(delta: LoadResult) {
    if (delta.chunk)          applyCommit(delta.chunk, true)    // chunk first
    if (delta.instanceValues) importInstanceValuesArray(delta.instanceValues)
    if (delta.imageValues)    importImageValuesArray(delta.imageValues)
    if (delta.fileValues)     importFileValuesArray(delta.fileValues)
    if (delta.state?.maxSequence > lastSequence.value) lastSequence.value = delta.state.maxSequence
    triggerRefs()
}
```

Export `lastSequence` and `applyDelta`.

### F3 — `apiProjectRoutes.ts`: add `apiGetDelta`

```ts
export async function apiGetDelta(since: number): Promise<LoadResult> {
    const res = await projectApi.get(`/delta?since=${since}`)
    return keysToCamel(res.data) as LoadResult
}
```

### F4 — `socketStore.ts`: handle `'db_update'`

```ts
let isSyncing = false

socket.on('db_update', async () => {
    const dataStore = useDataStore()
    if (!dataStore.isLoaded || isSyncing) return
    isSyncing = true
    try {
        const delta = await apiGetDelta(dataStore.lastSequence)
        dataStore.applyDelta(delta)
    } finally {
        isSyncing = false
    }
})
```

Remove the broken `'commit'` handler.

## Frontend handling of `empty_*` from delta

The backend sends `empty_instance_values` as `[[prop_id, inst_id], ...]`. Frontend `applyCommit` expects `emptyInstanceValues: InstancePropertyValue[]`. The `keysToCamel` transform on the response will turn `empty_instance_values` into `emptyInstanceValues` but the inner arrays stay as `[number, number]`. Need to map in `applyCommit` or in the delta's `chunk` parsing:

```ts
// When applying chunk from delta, normalize empty value lists:
if (chunk.emptyInstanceValues) {
    // already [{propertyId, instanceId}] if backend sends objects
    // OR need: chunk.emptyInstanceValues = chunk.emptyInstanceValues.map(([p,i]) => ({propertyId:p, instanceId:i}))
}
```

**Decision**: have the backend send objects `{property_id, instance_id}` (not arrays) for `empty_*` value lists, matching the existing `DbCommit` frontend format. Simpler parsing.

## Ordering constraint

1. B1 (stream_models.py: add fields)
2. B2 (stream endpoint: capture start_sequence)
3. B3 → B4 (watcher + server: switch to sequence, emit 'db_update')
4. B5 → B6 (data_reader + delta endpoint)
5. F1 → F2 → F3 → F4 (frontend)

## What this does NOT change

- `sendCommit` / `applyCommit` for local writes — already applied optimistically
- The initial stream (`apiStreamLoadState`) — unchanged, still the full initial load
- The `'tasks'` socket event — unchanged
- On reconnect: `init()` restarts the full stream and resets `lastSequence`
