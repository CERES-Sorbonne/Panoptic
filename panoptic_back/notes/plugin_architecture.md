# Plugin Architecture — current vs new

---

## How plugins work today (current async code)

### Entry point

Each plugin is a Python package with an `__init__.py` that exports:

```python
plugin_class = MyPlugin  # required sentinel
```

`LoadPluginTask` imports the module, reads `plugin_class`, and instantiates it:

```python
plugin_class(project=project, plugin_path=path, name=key.name)
```

### `APlugin` base class (`panoptic/core/plugin/plugin.py`)

```python
class APlugin:
    name: str
    _project: Project          # raw Project (for internals)
    project: PluginProjectInterface  # safe wrapper (for plugin author use)
    plugin_path: str
    data_path: Path            # <project>/plugin_data/<slug>/
    params: Any | None         # Pydantic BaseModel, persisted to DB
    registered_functions: List[FunctionDescription]

    async def start() → calls _start()
    async def _start()   # override point
    async def update_params(params)
```

Lifecycle:

1. `__init__` — register actions with `add_action_easy` / `add_action`
2. `start()` — loads params from DB, loads vector types, calls `_start()`
3. `_start()` — plugin-specific init (download models, warmup, etc.)

### Action registration

```python
self.add_action_easy(self.my_function, hooks=['execute', 'similar', 'group'])
```

- Introspects function signature automatically
- Extracts descriptions from docstring (`@param_name: description`)
- Generates ID: `{plugin_name}.{function_name}`
- `hooks` controls where the action appears in the UI

Function signature requirements:
- Must be `async def`
- First arg: `context: ActionContext` (carries `instance_ids`, `group_name`, `ui_inputs`)
- Other args: typed with allowed types: `int`, `float`, `str`, `bool`, `Path`, `PropertyId`, `Enum`, `VectorType`, `OwnVectorType`, `InputFile`
- Returns: `ActionResult`

```python
async def ocr(self, context: ActionContext, language: str = 'en') -> ActionResult:
    """Run OCR on selected images.
    @language: ISO language code
    """
    ...
    return ActionResult(groups=[...], notifs=[...])
```

### `PluginProjectInterface`

A safe wrapper around `Project` exposed as `self.project` to plugin authors.
`self._project` is the raw Project (used internally only).

Key methods:
```python
async get_instances(ids, sha1s) → list[Instance]
async get_properties(ids, computed) → list[Property]
async get_tags(ids, property_ids) → list[Tag]
async get_instance_property_values(property_ids, instance_ids) → list[...]
async get_image_property_values(property_ids, sha1s) → list[...]
async get_vectors(type_id, sha1s) → list[Vector]
async get_or_create_property(name, type_, mode) → Property
async do(commit: DbCommit) → Commit   # undo-queue aware
async add_vector(vector: Vector)
def add_task(task: Task)
def on_instance_import(callback)
def on_folder_delete(callback)
base_path: Path
```

### `ActionResult`

```python
@dataclass
class ActionResult:
    groups:  list[Group]  = None  # grouped instance IDs / sha1s with scores
    datas:   list[dict]   = None  # generic data
    urls:    list[str]    = None  # URLs to display
    notifs:  list[Notif]  = None  # DEBUG / INFO / WARNING / ERROR
    value:   Any          = None
```

### Loading flow

```
Panoptic.load_project(uid)
  └─ Project(path, plugins, name)
       └─ project.start()
            └─ LoadPluginTask (async Task)
                 for each PluginKey:
                   import module  → plugin_class
                   plugin = plugin_class(project, path, name)
                   await plugin.start()
                   project.add_plugin(plugin)
```

### Routes

Actions are called via REST (not Socket.IO):

```
POST /project/{id}/action_execute
    body: { function: "MacOCR.ocr", context: { instance_ids: [...] } }

GET  /project/{id}/actions
    → { "MacOCR.ocr": FunctionDescription, ... }

GET  /project/{id}/plugins_info
    → list of PluginDescription
```

### Per-plugin storage

- Data directory: `<project_folder>/plugin_data/<plugin_slug>/`
- DB params: key-value in project DB, namespaced `{plugin_name}.base`
- Vector types namespaced by plugin source

---

## What changes for the new sync architecture

### Core changes

| Concern | Current | New |
|---|---|---|
| Plugin functions | `async def` | `def` (sync) or can stay async if run via task |
| `APlugin._start()` | `async def` | `def` |
| `PluginProjectInterface` methods | `async def` | `def` (wraps `Project2` sync methods) |
| `LoadPluginTask` | async Task | sync Task (inherits from `Task` in panoptic2) |
| Project reference | old `Project` | `Project2` |
| DB param storage | async KV | sync ProjectDB KV (or new key-value schema) |

### What stays the same

- `plugin_class` sentinel in `__init__.py` — unchanged
- `add_action_easy` introspection pattern — unchanged
- `hooks` list for UI placement — unchanged
- `ActionContext` and `ActionResult` models — unchanged
- `data_path` per-plugin directory — unchanged
- REST route structure — unchanged

### New `APlugin` base (proposed)

```python
class APlugin:
    def __init__(self, name: str, project: Project2, plugin_path: str):
        self.name = name
        self._project = project
        self.plugin_path = plugin_path
        self.data_path = project.folder / 'plugin_data' / _slug(name)
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.registered_functions: list[FunctionDescription] = []
        # subclass __init__ calls add_action_easy here

    def start(self):
        self._start()   # override point

    def _start(self):
        pass            # plugin override

    def add_action_easy(self, fn: Callable, hooks: list[str] = None) -> FunctionDescription:
        ...  # same introspection logic, stores sync callable
```

### New `PluginProjectInterface` (proposed)

Thin sync wrapper over `Project2`. Exposes only what plugin authors need:

```python
class PluginProjectInterface:
    def __init__(self, project: Project2):
        self._project = project

    def get_instances(self, ids=None, sha1s=None) → list[Instance]:
        return self._project.get_instances(...)

    def get_properties(self, ...) → list[Property]: ...
    def apply_commit(self, commit: UpsertCommit) → Commit: ...
    def add_task(self, task: Task): ...
    # events: call_soon_threadsafe bridge needed for on_instance_import etc.

    @property
    def base_path(self) -> Path:
        return self._project.folder
```

### Action execution (sync)

Actions are currently `async def` because the old project was async.
In the new architecture, plugin action functions are plain `def`.
They run in a thread via `TaskManager` (same as any long-running work).

```python
def ocr(self, context: ActionContext, language: str = 'en') -> ActionResult:
    """Run OCR on images.
    @language: ISO language code
    """
    instances = self.project.get_instances(ids=context.instance_ids)
    ...
    return ActionResult(groups=[...])
```

The route calls the action synchronously from a FastAPI thread-pool worker, or submits it as a Task if it's long-running.

### `LoadPluginTask` (new sync Task)

```python
class LoadPluginTask(Task):
    def __init__(self, project: Project2, plugin_keys: list[PluginKey]):
        super().__init__()
        self._project = project
        self._plugin_keys = plugin_keys

    def start(self):
        for key in self._plugin_keys:
            module = _import_plugin(key)
            plugin = module.plugin_class(
                project=self._project,
                plugin_path=key.install_path,
                name=key.id,
            )
            plugin.start()
            self._project.add_plugin(plugin)  # register with project
```

### Plugin loading flow (new)

```
Panoptic2.load_project(uid)
  └─ Project2.start()        ← creates folder, seeds DBs
     project.add_task(LoadPluginTask(project, plugin_keys))
       └─ LoadPluginTask.start()
            for each PluginKey:
              import → plugin_class
              plugin = plugin_class(project2, path, name)
              plugin.start()
              project2.add_plugin(plugin)
```

`Project2` needs `plugins: list[APlugin]` and `add_plugin(plugin)` method.

### Events / callbacks

Current code has `on_instance_import` and `on_folder_delete` callbacks on the project interface.
In the new architecture:

- Callbacks are sync callables registered on `Project2`
- When the triggering write happens (inside `DataWriter`), the project iterates registered callbacks
- If the callback needs to emit a Socket.IO event it uses the `call_soon_threadsafe` bridge (same pattern as task updates)

### Open questions before implementing

1. **Where does `Project2.add_plugin()` store plugins?** — add `self.plugins: list[APlugin] = []` and `add_plugin(p)` to `Project2`.
   
   A: actually the plugins to load should be given in the project constructor. Plugins are already installed from the Panoptic class. So the install path should be known.
   
1. **When does `LoadPluginTask` run?** — inside `Project2.start()` (if plugin keys are passed to the constructor) or triggered externally by `Panoptic2.load_project`. Prefer passing plugin keys to `Project2.__init__` to keep the loading self-contained.
   
   A: The LoadPluginTask should be started at project start if any plugin is given.
   
1. **How does `PluginProjectInterface` expose events?** — `Project2` keeps a list of registered callbacks per event type. Plugins register via `self.project.on_instance_import(cb)`. The trigger sites in `Project2` (after a successful write) call the callbacks synchronously in the write thread.
   
   A: the project class is responsible to trigger thoses events. If instances are added from an outside script the plugins are not expected to react to it. Later we could do a trigger from the dbwatcher but it is not usefull now.
   
1. **Param storage** — The old code uses a key-value table in the project DB. `ProjectDB` already has a `key_value` mechanism (from `key_value_schema.py`). Reuse that — namespaced by plugin name.
   
   A: yes. The project db key value storage should be used to store differents plugin params per project
   
1. **FunctionDescription and introspection** — these are UI models only. They can be copied from the old code with minimal changes (remove async assumptions).
   
   A: yes. But always copy the models used to the new folder if they are usefull. In this case it already filters out the unused ones

---

## Files to create / modify

```
panoptic2/
  core/
    plugin/
      plugin.py              ← APlugin base class (sync)
      plugin_interface.py    ← PluginProjectInterface (wraps Project2)
      load_plugin_task.py    ← LoadPluginTask (sync Task)
      action_registry.py     ← ActionRegistry (introspection, call dispatch)
  models/
    action_models.py         ← ActionContext, ActionResult, FunctionDescription, Group, Notif
```

`Project2` additions:
- `__init__`: accept `plugin_keys: list[PluginKey] = None`
- `start()`: if `plugin_keys`, create and enqueue `LoadPluginTask`
- `add_plugin(plugin: APlugin)`
- `plugins: list[APlugin]`
- `action: ActionRegistry`
- `on_instance_import(cb)` / `on_folder_delete(cb)` registration
