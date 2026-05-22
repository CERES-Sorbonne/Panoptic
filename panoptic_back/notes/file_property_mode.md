# File Property Mode

## What it is

A new property mode `file` that stores one value **per file** (keyed by `file_id`).

### Mode comparison

| Mode     | Key             | Shared across…                         | Use case                                        |
|----------|-----------------|----------------------------------------|-------------------------------------------------|
| `id`     | instance_id     | nothing — strictly per instance        | annotations that differ between instances       |
| `sha1`   | sha1            | all files with identical content       | image-level metadata (dimensions, embeddings)   |
| `file`   | file_id         | all instances that point to same file  | file-level metadata (filename tags, path notes) |

`file` is between `sha1` and `id`: duplicate images (same sha1) can carry different file-level values if they live in different files, but all instances of the same file share a single value.

---

## Changes required

### 1. Backend — data models (`panoptic/models/data.py`)

Add `FileValue` struct (mirrors `InstanceValue` / `Sha1Value`):

```python
class FileValue(msgspec.Struct, array_like=True):
    property_id: Annotated[int, PrimaryKey]
    file_id:     Annotated[int, PrimaryKey]
    value: Any   # handled as JSON
    commit_id:   Optional[int] = None
    operation:   Optional[int] = None
```

Add `file_values` to `UpsertCommit`:

```python
class UpsertCommit(msgspec.Struct):
    ...
    file_values: dict[int, list[FileValue]] = msgspec.field(default_factory=dict)
```

### 2. Backend — property mode enum (`panoptic/models/models.py`)

```python
class PropertyMode(Enum):
    id   = 'id'
    sha1 = 'sha1'
    file = 'file'          # ← new
```

### 3. Backend — DB schema (`panoptic/core/databases/data/create.py`)

```python
from panoptic.models.data import FileValue

FILE_VALUES_SCHEMA = PropertyValueSchema(FileValue, table="file_values")
```

Add `FILE_VALUES_SCHEMA` to `datastore_desc` (the `DbDescription` list).

Also add a DB migration (version bump) to CREATE the `file_values` table for existing databases.

### 4. Backend — data reader (`panoptic/core/databases/data/data_reader.py`)

```python
def get_file_values(self, **filters) -> List[FileValue]:
    return FILE_VALUES_SCHEMA.get(self.conn, **filters)
```

### 5. Backend — data writer (`panoptic/core/databases/data/data_writer.py`)

In `apply_upsert_commit`, add the call:
```python
self._upsert_commit_file_values(tx, data, commit_id, seq_number)
```

New method (same pattern as `_upsert_commit_instance_values`):
```python
def _upsert_commit_file_values(self, tx, data, commit_id, sequence):
    if not data.file_values:
        return
    all_values = [v for values in data.file_values.values() for v in values]
    set_commit(all_values, commit_id)
    FILE_VALUES_SCHEMA.upsert(tx, objs=all_values, sequence=sequence)
    FILE_VALUES_SCHEMA.append_log(tx, objs=all_values, commit_id=commit_id)
```

### 6. Backend — project (`panoptic2/core/project/project.py`)

```python
def get_file_values(self, **filters):
    with self._data_reader() as r:
        return r.get_file_values(**filters)
```

### 7. Backend — stream models (`panoptic2/models/stream_models.py`)

Add `FileValuesColumn`:
```python
class FileValuesColumn(msgspec.Struct):
    property_id: int
    file_ids: list[int]
    values: list[str]   # JSON-encoded, same pattern as the other columns
```

Update `LoadState` to track file values:
```python
finished_file_values: bool = False
counter_file_value: int = 0
max_file_value: int = 0
```

Update `StreamResult`:
```python
file_values: Optional[list[FileValuesColumn]] = None
```

### 8. Backend — routes (`panoptic2/routes/project_routes.py`)

**`GET /db_state_stream`** — chunk 3 already handles values; add file_values alongside:
```python
file_values = project.get_file_values()
fv_cols: dict[int, FileValuesColumn] = {}
for fv in file_values:
    col = fv_cols.setdefault(fv.property_id, FileValuesColumn(fv.property_id, [], []))
    col.file_ids.append(fv.file_id)
    col.values.append(json.dumps(fv.value))
# yield them in the final StreamResult
```

**`POST /commit/upsert`** — add `_FVIn` model and wire into `UpsertRequest`:
```python
class _FVIn(BaseModel):
    property_id: int
    file_id: int
    value: Any = None

class UpsertRequest(BaseModel):
    ...
    file_values: list[_FVIn] = []
```

In the handler, group by property_id and append `FileValue` objects to `upsert.file_values`.

### 9. Backend — `DELETE /commit/delete` (`panoptic2/routes/project_routes.py`)

Add `DeleteCommit` support for file values when needed (can be deferred — write `null` value to effectively clear).

---

## Frontend changes

### 10. `models.ts`

```ts
export interface FilePropertyValue {
    propertyId: number
    fileId: number
    value: any
}

export interface FileValuesArray {
    propertyId: number
    fileIds: number[]
    values: any[]
}
```

In `DbCommit`:
```ts
fileValues?: FilePropertyValue[]
emptyFileValues?: FilePropertyValue[]
```

Add `PropertyMode.file = 'file'` to the enum (or wherever modes are defined).

### 11. `dataStore.ts`

**`importFileValues(values: FilePropertyValue[])`** — resolves `file_id` → instance(s) via a `fileIndex` (file_id → instance[]) and sets `instance.properties[propertyId]`. This requires a `fileIndex` similar to `sha1Index`:

```ts
const fileIndex = shallowRef<{ [fileId: number]: Instance[] }>({})
```

Build it during `importInstances` (need `file_id` on the instance — see note below).

**`applyCommit`** — add branches for `commit.fileValues` and `commit.emptyFileValues`.

**`setPropertyValue`** — add `file` mode branch:
```ts
if (mode == PropertyMode.file) {
    const values = images.map(i => ({ propertyId, fileId: i.fileId, value }))
    fileValues.push(...values)
}
```

**`sendCommit`** — include `fileValues` in the `hasUpsert` check.

### 12. `apiProjectRoutes.ts`

`apiCommitUpsert` — add `file_values` to the serialised payload:
```ts
if (commit.fileValues?.length)
    fixed.file_values = commit.fileValues.map(v => keysToSnake(v))
```

### 13. Stream load handler

In the `apiStreamLoadState` consumer (wherever `imageValues` is processed), add handling for `fileValues` in the same pattern.

---

## Open question — `fileId` on Instance

The frontend's `Instance` interface currently doesn't expose `file_id` — the stream join loses it:

```python
stream_instances.append(FullInstance(
    id=inst.id, sha1=inst.sha1, ...  # no file_id
))
```

To build `fileIndex` the frontend needs `file_id`. Two options:

1. **Add `fileId` to `FullInstance`** — cleanest, small wire overhead.
2. **Derive from URL** — the URL is already the full file path; `file_id` can be fetched on demand.

Option 1 is recommended. Add `file_id: Optional[int]` to `FullInstance` and include it in the stream.

---

## Implementation order

1. `FileValue` struct + `UpsertCommit.file_values`
2. `FILE_VALUES_SCHEMA` + DB migration
3. `DataReader.get_file_values` + `DataWriter._upsert_commit_file_values`
4. `PropertyMode.file` enum value
5. `Project2.get_file_values`
6. Stream model + route changes (server-side stream + commit/upsert route)
7. Add `fileId` to `FullInstance` + stream
8. Frontend models + `fileIndex` + `importFileValues`
9. `applyCommit` + `setPropertyValue` + `sendCommit` + `apiCommitUpsert`
