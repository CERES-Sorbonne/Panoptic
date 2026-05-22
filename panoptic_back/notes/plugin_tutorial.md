# How to Write a Panoptic2 Plugin

This is the reference I use when building or porting plugins. Everything here is based on the actual panoptic2 code.

---

## 1. Plugin structure

A plugin is a directory with an `__init__.py` that exports a `plugin_class` sentinel:

```
MyPlugin/
├── __init__.py          ← must export plugin_class
└── my_plugin.py         ← the actual plugin code
```

**`__init__.py`** — always exactly this:
```python
from .my_plugin import MyPlugin
plugin_class = MyPlugin
```

**`my_plugin.py`** — the plugin class inheriting from `APlugin`:
```python
from panoptic2.core.plugin.plugin import APlugin
from panoptic2.models.action_models import ActionContext, ActionResult

class MyPlugin(APlugin):
    """Short description shown in the UI."""

    def __init__(self, name: str, project, plugin_path: str):
        super().__init__(name=name, project=project, plugin_path=plugin_path)
        self.add_action_easy(self.my_action, ['execute'])

    def _start(self) -> None:
        pass  # called after params are loaded

    def my_action(self, context: ActionContext) -> ActionResult:
        return ActionResult()
```

---

## 2. `APlugin` — what the base gives you

After `super().__init__()` the following are available:

| Attribute | Type | Description |
|-----------|------|-------------|
| `self.name` | `str` | Plugin name (used as the action ID prefix and param namespace) |
| `self.project` | `PluginProjectInterface` | **The only way to interact with the project** |
| `self.plugin_path` | `str` | Directory where the plugin is installed |
| `self.data_path` | `Path` | `project_folder/plugin_data/<name>/` — use for local caches |
| `self.params` | model or `None` | Plugin config; set in `__init__` before `super().__init__()` |
| `self.vector_types` | `list[VectorType]` | Loaded in `start()` — all VectorType rows where `source == self.name` |
| `self.registered_functions` | `list[FunctionDescription]` | Auto-populated by `add_action_easy` |

**Lifecycle:**

```
LoadPluginTask calls:
  plugin.__init__(name, interface, plugin_path)   ← register actions + event hooks here
  plugin.start()                                  ← do not override
    _load_params()                                  ← merge stored params
    vector_types = project.get_vector_types(source=self.name)
    _start()                                      ← override this for init logic
```

---

## 3. Plugin params

Declare a Pydantic model and assign it to `self.params` **before** `super().__init__()`. Values are loaded from `project.db` automatically. The UI sends updates via `POST /plugin_params`.

```python
from pydantic import BaseModel

class Params(BaseModel):
    compute_on_import: bool = True
    model_name: str = 'openai/clip-vit-base-patch32'

class MyPlugin(APlugin):
    def __init__(self, name, project, plugin_path):
        self.params = Params()            # set BEFORE super().__init__
        super().__init__(name, project, plugin_path)
```

`self.params` is the live object. After `start()` it contains whatever was stored in the DB merged over the defaults. To update and persist:

```python
# From an action:
self.update_params({'compute_on_import': False})
```

---

## 4. Registering actions

Actions are the functions that appear in the UI context menus. Register them in `__init__` with `add_action_easy`:

```python
self.add_action_easy(self.my_fn, ['execute'])       # hook controls which menu
self.add_action_easy(self.cluster, ['group'])
self.add_action_easy(self.find_similar, ['similar'])
self.add_action_easy(self.make_map, ['map', 'execute'])
self.add_action_easy(self.create_type, ['vector_type'])
self.add_action_easy(self.compute, ['vector'])
```

**Available hooks:** `execute`, `group`, `similar`, `map`, `vector`, `vector_type`, `text_search`

### Action function signature

```python
def my_action(self, context: ActionContext, param1: int, param2: MyEnum) -> ActionResult:
    """What this action does — shown in the UI.
    @param1: description of param1
    @param2: description of param2
    """
    ...
    return ActionResult(...)
```

- First param is always `context: ActionContext` (carries `instance_ids`, `group_name`, `ui_inputs`)
- Additional params are introspected and rendered as UI controls
- Return type must be `ActionResult`
- The function ID is `f'{self.name}.{fn.__name__}'`

### Allowed param types

| Python type | UI widget |
|-------------|-----------|
| `int` | number input |
| `float` | float input |
| `str` | text input |
| `bool` | checkbox |
| `Path` | file picker |
| `PropertyId` | property selector |
| `Enum` subclass | dropdown |
| `OwnVectorType` | selector for THIS plugin's vector types |
| `VectorType` | selector for ALL vector types |
| `InputFile` | file upload (base64 encoded) |

```python
from enum import Enum
from panoptic2.models.action_models import ActionContext, ActionResult, OwnVectorType, PropertyId

class ModelEnum(Enum):
    clip = 'openai/clip-vit-base-patch32'
    siglip = 'google/siglip2-so400m-patch16-naflex'

def compute_vectors(self, context: ActionContext, vec_type: OwnVectorType, model: ModelEnum) -> ActionResult:
    """Compute image vectors.
    @vec_type: which vector space to compute into
    @model: which model to use
    """
    ...
```

---

## 5. `ActionResult` — what you can return

```python
from panoptic2.models.action_models import ActionResult, Group, Notif, NotifType, ScoreList

# Return grouped images
return ActionResult(groups=[
    Group(sha1s=['abc...', 'def...'], name='Cluster 1'),
    Group(ids=[1, 2, 3]),
])

# Return ranked results with scores
scores = ScoreList(min=0, max=1, values=[0.9, 0.7, 0.5], max_is_best=True)
return ActionResult(groups=[Group(sha1s=[...], scores=scores)])

# Return a notification
return ActionResult(notifs=[
    Notif(type=NotifType.INFO, name='done', message='Finished processing 42 images')
])
return ActionResult(notifs=[
    Notif(type=NotifType.ERROR, name='no_vectors', message='Compute vectors first')
])

# Return arbitrary data
return ActionResult(value={'custom': 'data'})
```

---

## 6. The two-tier action pattern

**Fast actions** (< ~500 ms) — run inline, return data directly:

```python
def cluster_by_size(self, context: ActionContext, size: int) -> ActionResult:
    ids = context.instance_ids or []
    groups = [Group(ids=ids[i:i+size]) for i in range(0, len(ids), size)]
    return ActionResult(groups=groups)
```

**Slow actions** (> ~500 ms) — submit a Task and return immediately. The FastAPI thread is freed; the UI gets progress via Socket.IO `tasks` events:

```python
def compute_vectors(self, context: ActionContext, vec_type: OwnVectorType) -> ActionResult:
    instances = self.project.get_instances(ids=context.instance_ids)
    for inst in instances:
        task = ComputeVectorTask(self, vec_type, inst)
        self.project.add_task(task)
    return ActionResult(notifs=[
        Notif(type=NotifType.INFO, name='started',
              message=f'Computing vectors for {len(instances)} images')
    ])
```

---

## 7. Writing a background Task

Inherit from `panoptic2.core.task.task.Task`. Override `start()` (not `run()`). Call `self._notify()` to push progress to the UI.

```python
from panoptic2.core.task.task import Task
from panoptic2.core.plugin.plugin_interface import PluginProjectInterface

class ComputeVectorTask(Task):
    def __init__(self, plugin, vec_type, instance):
        super().__init__()
        self.plugin    = plugin
        self.project   = plugin.project     # the interface — safe to hold
        self.vec_type  = vec_type
        self.instance  = instance
        self.name      = f'Compute {vec_type.params["model"]} ({vec_type.id})'
        # Append to key so on_last fires per vec_type, not per all ComputeVectorTask instances
        self.key      += f'_vec{vec_type.id}'

    def start(self) -> None:
        self.state.running = True
        self._notify()

        if not self.project.vector_exist(self.vec_type.id, self.instance.sha1):
            image_data = self._load_image()
            if image_data:
                vector_data = self.plugin.transformer.to_vector(image_data)
                from panoptic.core.databases.media.models import Vector
                self.project.upsert_vectors([Vector(
                    type_id=self.vec_type.id,
                    sha1=self.instance.sha1,
                    data=vector_data,
                )])

        self.state.done = 1
        self.state.total = 1
        self.state.running = False
        self.state.finished = True
        self._finished_event.set()
        self._notify()

    def on_last(self) -> None:
        """Called by TaskManager after the last task of this key finishes."""
        self.plugin.rebuild_index(self.vec_type)

    def _load_image(self) -> bytes | None:
        for f in self.project.get_files(id=self.instance.file_id):
            if f.name:
                with open(f.name, 'rb') as fh:
                    return fh.read()
        return None
```

### Task state fields

```python
self.state.total   = 100   # total units of work
self.state.done    = 42    # units completed so far
self.state.running = True  # currently executing
self.state.finished = True # all done
```

Call `self._notify()` whenever state changes — this triggers the Socket.IO broadcast.

### Cancellation

Check `self._cancel_event.is_set()` in long loops:

```python
for item in big_list:
    if self._cancel_event.is_set():
        break
    process(item)
    self.state.done += 1
    self._notify()
```

---

## 8. Reading and writing project data

All through `self.project` (the `PluginProjectInterface`):

```python
# Reads
instances       = self.project.get_instances(ids=[1, 2, 3])
all_instances   = self.project.get_instances()
properties      = self.project.get_properties()
tags            = self.project.get_tags(property_id=5)
sha1_values     = self.project.get_sha1_values(property_id=3)
instance_values = self.project.get_instance_values(property_id=3)

# Writes — source is automatically set to self.name
from panoptic.models.data import UpsertCommit, Sha1Value
from panoptic.core.databases.entity_schema import OP_UPDATE

commit = UpsertCommit()
commit.sha1_values[prop.id] = [
    Sha1Value(property_id=prop.id, sha1='abc...', value='hello', commit_id=0, operation=OP_UPDATE)
]
self.project.apply_upsert_commit(commit)
```

---

## 9. Vector types and vectors

```python
from panoptic.core.databases.media.models import VectorType, Vector

# Create a new vector type (id=-1 → auto-allocated)
vt = self.project.upsert_vector_type(
    VectorType(id=-1, source=self.name, params={'model': 'openai/clip-vit-base-patch32', 'greyscale': False})
)
# vt.id is now the real allocated id; self.vector_types is updated in start()

# Read existing types for this plugin
my_types = self.project.get_vector_types(source=self.name)

# Check if a vector exists
exists = self.project.vector_exist(type_id=vt.id, sha1='abc...')

# Write vectors
self.project.upsert_vectors([
    Vector(type_id=vt.id, sha1='abc...', data=numpy_array),
    Vector(type_id=vt.id, sha1='def...', data=numpy_array2),
])

# Read vectors
vectors = self.project.get_vectors(type_id=vt.id, sha1s=['abc...', 'def...'])
all_vectors = self.project.get_vectors(type_id=vt.id)
```

---

## 10. Maps (2D point clouds for PaCMAP / UMAP / t-SNE)

```python
from panoptic.core.databases.media.models import Map

# Create — id=-1 → auto-allocated
# data is a flat list: [sha1, x, y, sha1, x, y, ...]
flat = []
for sha1, (x, y) in points.items():
    flat += [sha1, x, y]

map_ = self.project.upsert_map(Map(
    id=-1,
    source=self.name,
    name='My PaCMAP',
    key='sha1',
    count=len(points),
    data=flat,
))
# map_.id is the real id

# List / delete
maps = self.project.get_maps()
self.project.delete_map(map_.id)
```

---

## 11. CPU-heavy work

For operations that would block the request for seconds (clustering, dimensionality reduction), use `run_in_executor`. Since actions run in FastAPI's thread pool (they're `def` routes), this just calls the function directly — you're already in a thread, not on the event loop:

```python
def compute_tsne(self, context: ActionContext, vec_type: OwnVectorType) -> ActionResult:
    instances = self.project.get_instances(ids=context.instance_ids)
    sha1s = list({i.sha1 for i in instances})
    vectors = self.project.get_vectors(type_id=vec_type.id, sha1s=sha1s)

    # Blocks this thread until done — other requests are served concurrently
    points = self.project.run_in_executor(self._compute_tsne, vectors)

    map_ = self.project.upsert_map(Map(id=-1, source=self.name, name='t-SNE', key='sha1',
                                       count=len(points), data=self._flatten(points)))
    return ActionResult(value=map_)

@staticmethod
def _compute_tsne(vectors):
    import numpy as np
    from sklearn.manifold import TSNE
    data = np.array([v.data for v in vectors])
    result = TSNE(n_components=2).fit_transform(data)
    return {vectors[i].sha1: result[i].tolist() for i in range(len(vectors))}
```

For very long operations (minutes), prefer the Task pattern instead.

---

## 12. Event hooks

Register in `__init__`. The callbacks receive lists, not single items.

```python
def __init__(self, name, project, plugin_path):
    super().__init__(name, project, plugin_path)
    self.project.on_instance_import(self._on_import)
    self.project.on_folder_delete(self._on_delete)

def _on_import(self, instances: list) -> None:
    if not self.params.compute_on_import:
        return
    for inst in instances:
        for vt in self.vector_types:
            self.project.add_task(ComputeVectorTask(self, vt, inst))

def _on_delete(self, folders: list) -> None:
    # Rebuild index after folder deletion removes sha1s
    for vt in self.vector_types:
        self.rebuild_index(vt)
```

---

## 13. Local data storage

`self.data_path` is `project_folder/plugin_data/<slug>/` and is created automatically. Use it for caches that should live with the project:

```python
import pickle
from pathlib import Path

def _save_cache(self, key: str, data) -> None:
    path = self.data_path / f'{key}.pkl'
    with open(path, 'wb') as f:
        pickle.dump(data, f)

def _load_cache(self, key: str):
    path = self.data_path / f'{key}.pkl'
    if path.exists():
        with open(path, 'rb') as f:
            return pickle.load(f)
    return None
```

---

## 14. Minimal complete example

```python
# simple_tagger/my_tagger.py
from pydantic import BaseModel
from panoptic2.core.plugin.plugin import APlugin
from panoptic2.models.action_models import ActionContext, ActionResult, Notif, NotifType

class Params(BaseModel):
    tag_prefix: str = 'auto'

class SimpleTagger(APlugin):
    """Tags images with a prefix based on their filename."""

    def __init__(self, name, project, plugin_path):
        self.params = Params()
        super().__init__(name, project, plugin_path)
        self.add_action_easy(self.tag_by_filename, ['execute'])

    def tag_by_filename(self, context: ActionContext) -> ActionResult:
        """Tag selected images using their filename.
        """
        from panoptic.models.data import UpsertCommit, Sha1Value
        from panoptic.core.databases.entity_schema import OP_UPDATE

        instances = self.project.get_instances(ids=context.instance_ids)
        files = {f.id: f for f in self.project.get_files()}
        properties = {p.name: p for p in self.project.get_properties()}

        prop = properties.get('Filename Tag')
        if prop is None:
            return ActionResult(notifs=[
                Notif(NotifType.ERROR, name='no_prop', message='Create a "Filename Tag" property first')
            ])

        commit = UpsertCommit()
        values = []
        for inst in instances:
            f = files.get(inst.file_id)
            if f and f.name:
                import os
                tag = f'{self.params.tag_prefix}:{os.path.basename(f.name)}'
                values.append(Sha1Value(
                    property_id=prop.id, sha1=inst.sha1,
                    value=tag, commit_id=0, operation=OP_UPDATE,
                ))
        commit.sha1_values[prop.id] = values
        self.project.apply_upsert_commit(commit)

        return ActionResult(notifs=[
            Notif(NotifType.INFO, name='done', message=f'Tagged {len(values)} images')
        ])
```

```python
# simple_tagger/__init__.py
from .my_tagger import SimpleTagger
plugin_class = SimpleTagger
```

---

## 15. Installing and registering

Plugins are registered at the Panoptic level (not per-project). Via HTTP:

```
POST /plugins
{
  "name": "SimpleTagger",
  "source": "/path/to/simple_tagger",
  "source_type": "path"
}
```

Source types: `"path"` (local dir), `"git"` (GitHub URL), `"pip"` (package name).

Once registered, the plugin is loaded when its project is opened. It appears in `/plugins_info` and its actions appear in `/actions`.

To update params at runtime:
```
POST /projects/{id}/plugin_params
{"plugin": "SimpleTagger", "params": {"tag_prefix": "img"}}
```
