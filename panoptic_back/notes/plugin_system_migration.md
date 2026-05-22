# Plugin System — Migration Analysis & Plan (panoptic → panoptic2)

Reference plugin: `PanopticML` (`/Users/david/PanopticML/panopticml/panoptic_ml.py`)

---

## 1. Core Design Principle: Interface as Safety Net

The `PluginProjectInterface` is the only thing a plugin ever sees. It must be self-contained — holding DB path references directly and opening its own connections, never delegating through `Project2`. This makes it a real boundary: if a method isn't on the interface, a plugin simply cannot do it.

**Current problem** (panoptic2 as-is):
```python
class APlugin:
    def __init__(self, name, project: Project2, plugin_path):
        self._project = project                  # raw Project2 — plugin can reach anything
        self.project = PluginProjectInterface(project)  # thin wrapper, easy to bypass
```

**Target design**:
```python
class APlugin:
    def __init__(self, name, project: PluginProjectInterface, plugin_path):
        self.project = project   # the interface IS the project — nothing else accessible
```

The plugin constructor receives a `PluginProjectInterface` already built. `Project2` is never passed to a plugin. `self._project` disappears from `APlugin`.

---

## 2. New `PluginProjectInterface` Constructor

The interface holds DB paths and the minimal live references it needs (task manager, action registry, event-registration callbacks). No reference to `Project2`.

```python
class PluginProjectInterface:
    def __init__(
        self,
        plugin_name: str,
        base_path: Path,
        data_db_path: Path,
        media_db_path: Path,
        project_db_path: Path,
        task_manager: TaskManager,
        action_registry: ActionRegistry,
        register_instance_import: Callable,
        register_folder_delete: Callable,
    ):
        self._name         = plugin_name
        self.base_path     = base_path
        self._data_path    = Path(data_db_path)
        self._media_path   = Path(media_db_path)
        self._project_path = Path(project_db_path)
        self._tasks        = task_manager
        self._actions      = action_registry
        self._reg_import   = register_instance_import
        self._reg_delete   = register_folder_delete
```

DB helpers are internal and mirror the Project2 pattern:
```python
    def _data_reader(self):  return DataReader(str(self._data_path))
    def _data_writer(self):  return DataWriter(str(self._data_path))
    def _media_db(self):     return MediaDB(str(self._media_path), datastore_desc)
    def _project_db(self):   return ProjectDB(self._project_path)
```

### Factory on `Project2`

`Project2` builds interfaces for plugins via a factory method. This is the only point of contact between the two worlds:

```python
# panoptic2/core/project/project.py

def make_plugin_interface(self, plugin_name: str) -> PluginProjectInterface:
    return PluginProjectInterface(
        plugin_name=plugin_name,
        base_path=self.folder,
        data_db_path=self.data_db_path,
        media_db_path=self.media_db_path,
        project_db_path=self.project_db_path,
        task_manager=self.task_manager,
        action_registry=self.action,
        register_instance_import=self.on_instance_import,
        register_folder_delete=self.on_folder_delete,
    )
```

### `LoadPluginTask` creates the interface before instantiating the plugin

```python
# panoptic2/core/plugin/load_plugin_task.py — in the loop

interface = self._project.make_plugin_interface(key.id)
plugin = module.plugin_class(
    project=interface,          # interface, NOT Project2
    plugin_path=key.install_path,
    name=key.id,
)
```

---

## 3. Full Interface API (target state)

### Read — data.db

```python
def get_folders(self, **filters) -> list[Folder]
def get_files(self, **filters) -> list[File]
def get_instances(self, **filters) -> list[Instance]
def get_properties(self, **filters) -> list[Property]
def get_tags(self, **filters) -> list[Tag]
def get_instance_values(self, **filters) -> list[InstanceValue]
def get_sha1_values(self, **filters) -> list[Sha1Value]
def get_file_values(self, **filters) -> list[FileValue]
```

All open `DataReader`, query, close.

### Write — data.db

```python
def apply_upsert_commit(self, commit: UpsertCommit, group_id: int = None) -> Commit
def apply_delete_commit(self, commit: DeleteCommit, group_id: int = None) -> Commit
```

**Source is always the plugin name — automatically set, cannot be spoofed:**
```python
def apply_upsert_commit(self, commit, group_id=None):
    with self._data_writer() as w:
        return w.apply_upsert_commit(self._name, commit, group_id=group_id)
```

### Read/Write — media.db (vectors, maps)

```python
def get_vector_types(self, source: str = None) -> list[VectorType]
def upsert_vector_type(self, vt: VectorType) -> VectorType    # returns saved with assigned id
def delete_vector_type(self, type_id: int) -> None

def get_vectors(self, type_id: int, sha1s: list[str] = None) -> list[Vector]
def upsert_vectors(self, vectors: list[Vector]) -> None
def vector_exist(self, type_id: int, sha1: str) -> bool

def get_maps(self, **filters) -> list[Map]
def upsert_map(self, map_: Map) -> Map                         # returns saved with assigned id
def delete_map(self, map_id: int) -> None
```

### Params — project.db (namespaced automatically)

Used internally by `APlugin._load_params()` and `update_params()`. Not typically called directly by plugin authors.

```python
def load_params(self) -> dict | None
    # reads user_defaults where user_id='plugin.<name>', key='params'

def save_params(self, params: dict) -> None
    # writes user_defaults where user_id='plugin.<name>', key='params'
```

### Tasks

```python
def add_task(self, task: Task, high_priority: bool = False) -> Task
```

### Events

```python
def on_instance_import(self, callback: Callable[[list[Instance]], None]) -> None
def on_folder_delete(self, callback: Callable[[list[Folder]], None]) -> None
```

### Actions (used by APlugin — not called directly by plugin authors)

```python
def register_action(self, fn: Callable, hooks: list[str] = None) -> FunctionDescription
    # builds FunctionDescription with id = f'{self._name}.{fn.__name__}'
    # registers in action_registry
```

### CPU executor

```python
def run_in_executor(self, fn: Callable, *args) -> Any
    # Runs fn(*args) in a thread/process pool, blocking the caller.
    # Use for CPU-heavy work (clustering, dimensionality reduction).
    # Simple first implementation: concurrent.futures.ThreadPoolExecutor(1)
    # Upgrade path: ProcessPoolExecutor for GIL-bound work.
```

---

## 4. Updated `APlugin` base class

```python
class APlugin(ABC):
    def __init__(self, name: str, project: PluginProjectInterface, plugin_path: str):
        self.name          = name
        self.project       = project        # the interface — only thing accessible
        self.plugin_path   = plugin_path
        self.params: Any   = None
        self.vector_types: list = []        # populated in start() from DB

        slug = '_'.join(name.split()).lower()
        self.data_path = project.base_path / 'plugin_data' / slug
        self.data_path.mkdir(parents=True, exist_ok=True)

        self.registered_functions: list[FunctionDescription] = []

    def start(self) -> None:
        self._load_params()
        self.vector_types = self.project.get_vector_types(source=self.name)
        self._start()

    def _start(self) -> None:
        """Override for plugin-specific initialisation."""

    def _load_params(self) -> None:
        if self.params is None:
            return
        stored = self.project.load_params()   # goes through interface, not Project2
        if stored:
            try:
                self.params = self.params.__class__(**{**self.params.dict(), **stored})
            except Exception:
                pass

    def update_params(self, params) -> Any:
        if self.params is not None and isinstance(self.params, BaseModel):
            self.params = self.params.model_copy(
                update=params if isinstance(params, dict) else params.dict()
            )
        self.project.save_params(self.params.dict() if self.params else {})
        return self.params

    def add_action_easy(self, fn: Callable, hooks: list[str] = None) -> FunctionDescription:
        desc = self.project.register_action(fn, hooks)
        self.registered_functions.append(desc)
        return desc

    def add_action(self, fn: Callable, description: FunctionDescription) -> FunctionDescription:
        # explicit description variant — still registers through interface
        self.project._actions.add(fn, description)
        self.registered_functions.append(description)
        return description
```

Key changes vs current:
- No `self._project` — the raw `Project2` is never held
- `_load_params()` / `update_params()` use `self.project.load_params()` / `save_params()`
- `add_action_easy()` uses `self.project.register_action()` (not `self._project.action`)
- `self.vector_types` populated in `start()` via `self.project.get_vector_types(source=self.name)`
- `self.data_path` built from `project.base_path` (interface exposes this)

---

## 5. What changes in each file

| File | Change |
|------|--------|
| `panoptic2/core/plugin/plugin_interface.py` | Full rewrite: hold paths + minimal live refs, implement all DB methods directly |
| `panoptic2/core/plugin/plugin.py` | Constructor takes `PluginProjectInterface` not `Project2`; remove `self._project`; route params/actions through interface |
| `panoptic2/core/project/project.py` | Add `make_plugin_interface(plugin_name)` factory method |
| `panoptic2/core/plugin/load_plugin_task.py` | Call `project.make_plugin_interface(key.id)` before instantiating the plugin class |
| `panoptic2/core/plugin/action_registry.py` | Refactor `build_function_description(plugin, fn, hooks)` to accept a `str` name in addition to an `APlugin`, so the interface can build descriptors without holding the plugin object |
| `panoptic2/routes/project_routes.py` | Add `POST /plugin_params` route (calls `project.update_plugin_params`) |
| `panoptic2/core/project/project.py` | Add `update_plugin_params(plugin_name, params)` |
| `panoptic2/core/task/task.py` | Add `on_last()` hook (called when last task of a given `key` finishes) |
| `panoptic2/core/task/task_manager.py` | Call `task.on_last()` when last task of a key completes |
| `panoptic2/core/server/panoptic_server.py` | Verify `on_update` → Socket.IO uses `loop.call_soon_threadsafe` |

---

## 6. Threading and Non-Blocking: `action_execute`

The route is `def execute_action(...)` — FastAPI runs it in its thread pool. The event loop is never blocked. This is already correct.

**Fast actions** run inline and return data immediately. **Slow actions** submit a `Task` and return a notification:

```python
def compute_vectors(self, context: ActionContext, vec_type: OwnVectorType) -> ActionResult:
    for inst in self.project.get_instances(ids=context.instance_ids):
        self.project.add_task(ComputeVectorTask(self, vec_type, inst))
    return ActionResult(notifs=[Notif(NotifType.INFO, name='started', message='Computing...')])
```

The `TaskManager` worker thread picks up tasks. Progress reaches the UI via Socket.IO `task_update` events (pending Step 7 verification).

---

## 7. `on_last()` hook for TaskManager

PanopticML rebuilds its Faiss tree after all `ComputeVectorTask` instances for a given vector type finish. In the old system this was `run_if_last()`. In panoptic2:

Add to `Task` base:
```python
def on_last(self) -> None:
    """Called by TaskManager after the last task of this key finishes."""
    pass
```

`TaskManager._run_wrapper` after finishing a task: check `_tasks` for any remaining task with the same `key`. If none remain (pending or running), call `task.on_last()`.

`ComputeVectorTask` overrides `on_last()` to call `self.plugin.trees.rebuild_tree(self.vec_type)`.

---

## 8. PanopticML Migration Checklist

Once the above is implemented:

- [ ] Change imports to panoptic2
- [ ] Constructor receives `PluginProjectInterface` directly (not `Project2`)
- [ ] All `async def` → `def`, remove all `await`
- [ ] `await self.project.get_instances(...)` → `self.project.get_instances(...)`
- [ ] `await self.project.get_vectors(...)` → `self.project.get_vectors(...)`
- [ ] `await self.project.add_vector_type(...)` → `self.project.upsert_vector_type(...)`
- [ ] `await self.project.run_async(fn, *args)` → `self.project.run_in_executor(fn, *args)`
- [ ] `await self.project.create_map(...)` + `await self.project.add_map(...)` → `self.project.upsert_map(...)`
- [ ] `self.vector_types` is now loaded automatically in `APlugin.start()` — remove manual loading from `_start()`
- [ ] Rewrite `ComputeVectorTask`: inherit panoptic2 `Task`, rename `run()` → `start()`, sync calls
- [ ] `ComputeVectorTask.run_if_last()` → `on_last()`
- [ ] `await self.transformers.async_get(...)` → `self.transformers.get(...)` (sync)
- [ ] `aiofiles.open(...)` → plain `open(..., 'rb')`
- [ ] `await asyncio.to_thread(fn)` → direct call (already in a thread)
