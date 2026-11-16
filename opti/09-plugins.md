# 09: Python plugins

Status 2026-11-06: proposal. Plugins stay in Python, so they stay easy to write and can use the
Python ML stack. The backend is Rust (README), so a plugin runs in its own Python process. The
backend calls its functions; while a function runs, the plugin reads and writes the project's
db files directly, through a Python plugin API. Sources: today's plugin interface
(`panoptic_back/panoptic/plugin.py`, `core/plugin/plugin_interface.py`,
`models/action_models.py`).

## 1. Principles

1. **Called, not running alongside.** A plugin works when the backend calls one of its
   functions: an action the user starts, a hook (§4), a clustering or a search the engine asks
   for (note 06 §8). Between calls it holds no lock and reads nothing.
2. **Direct file access.** The plugin API opens `data.db`, `media.db` and `project.db` itself
   (note 02 §5). No data goes through the backend's HTTP or socket API: a plugin reading 1M
   vectors or writing a 1M-row column pays only SQLite.
3. **No live updates.** A plugin reads the data as it is when it reads it. It does not follow
   the change feed. A function that needs one consistent view reads inside one read
   transaction.
4. **Same rules as the backend.** Writes to `data.db` go through the plugin API, which follows
   note 01 §7: one sequence per transaction, commits and `entity_log` rows, tombstones,
   `AUTOINCREMENT` ids. A plugin write is undoable like a user's.

## 2. Process model

- **One process per plugin**, in the plugin's own folder and virtual environment
  (`panoptic.db` `plugins.install_path`, note 02 §4), created with `uv` at install. Plugins
  cannot break each other's dependencies or the backend.
- **Started on the first call** for a project, kept alive while the project is open, so a model
  loaded once (CLIP, a detector) serves every call. Stopped on project close, after an idle
  time, or by `/plugin/stop`.
- **A crash ends the call, not the backend.** The backend reports the error and restarts the
  process on the next call. Rows already committed by the plugin stay, each batch being its
  own commit of the call's group (§5.3).
- **Description.** At start the process reports its functions with their parameters
  (`FunctionDescription`, `ParamDescription` as today) and their hooks. The description is
  cached in `panoptic.db` per installed version, so `/actions` and hooks work before the
  first call; a plugin starts once at install to fill it (note 00 §8.3). The backend pushes
  `plugins_info` when it changes (note 08 §4).

## 3. Calls

The backend and the plugin process exchange JSON messages over the process's stdin / stdout.

| message | direction | content |
|---|---|---|
| `call` | backend → plugin | call id, function, params, and the context: project folder (the paths of its db files), user, row kind and row ids (note 03 §7), group name, commit group id (§5.3) |
| `progress` | plugin → backend | call id, done / total, a message. Shown in the task panel (note 00 §7.3) |
| `notify` | plugin → backend | call id, a notification (`Notif`) |
| `cancel` | backend → plugin | call id. The plugin API raises `TaskCancelled` at the next read, write or progress call |
| `result` | plugin → backend | call id, `ActionResult`: groups (row ids, scores), scores per row, notifications, urls, a value; or an error |

- Today's `ActionContext.instance_ids` becomes the row kind and row ids, and `Group.sha1s`
  goes: groups and scores name rows of the call's row kind.
- **After `result`** the backend makes the store catch up on whatever the plugin wrote (note 05
  §6.1), publishes one version, and the clients get one batch of change events (note 08 §4).
  Media writes produce a `media.changed` event.
- One call at a time per plugin process by default. A plugin that declares itself reentrant
  gets concurrent calls.

## 4. Hooks

A function can declare hooks (today `FunctionDescription.hooks`). The backend calls it when the
event happens, as a task:

| hook | when | context |
|---|---|---|
| `on_import` | new images were added (an import or a rescan) | the new image ids |
| `on_purge` | images were purged (note 04 §6.6) | the purged image and subimage ids, so the plugin cleans its own stores |
| `on_project_open` | the project opened | none |

## 5. The plugin API

A Python package the plugin imports (today `panoptic.plugin`). It is the only part of a plugin
that knows the file layout.

### 5.1 Reads

- Schema: properties, property groups, tags, tag lists, folders, file sources.
- Rows: images (id, hash), files (id, image, folder, name, path, status), instances (id, key,
  image, file), subimages (id, image, namespace, box); the rows of the call's context; the
  image ids behind a set of rows.
- Values: one property's values as a dict or numpy arrays keyed by row id, read from one range
  of its value table (note 01 §3).
- Media: vectors of a type for a set of images or subimages (numpy, float32), thumbnails, maps.
- Its own `plugin_data` (note 02 §3).

### 5.2 Writes

- `ensure_property(key, name, dtype, mode)`: finds or creates the plugin's property (today's
  `ensure_property` / `adopt_property`, keyed in `plugin_data`).
- `ensure_tags(property, labels)`, `set_values(property, {row id: value})` for image, instance
  or subimage mode, `set_tags(property, {row id: [tag ids]})`.
- Subimages: `write_subimages(namespace, [(image id, box)])` with box rounding done by the API
  (note 01 §3, subimages), then values on the returned subimage ids.
- Boxes: `set_boxes(property, {row id: [(x0, y0, x1, y1, name, color)]})` for an image or
  instance `box` property. Each list replaces the row's cell whole, and an empty list deletes
  it. The API rounds, checks the shape and writes the JSON (note 01 §3, boxes). Reads return
  the same tuples. `cut_boxes(box_property, namespace)` turns the boxes into subimages (note
  01 §3, boxes).
- Media: `upsert_vectors(type, {image or subimage id: array})`, maps and their points.
- `plugin_data` get / set.

### 5.3 How writes reach the file

- Each `data.db` write is one transaction by the rules of note 01 §7, with
  `commits.source = 'plugin:<name>'` and the user of the call as `author`. A large write is cut
  into batches (note 01 §7, rule 6); every batch is one commit with the call's `group_id`, so
  the whole call is undone as one.
- There is no partial undo. A permanent delete (an instance, a file source, a purged image,
  note 01 §3, deletes) of any row a call wrote makes the whole call impossible to undo. Keeping
  that acceptable is the plugin author's job: a function writes one coherent result, and
  unrelated writes go in separate calls.
- Values are type-checked against the property before they are written (note 05 §3.2), so a
  plugin cannot store a TEXT in a number column.
- `media.db` and `plugin_data` writes are plain transactions: not undoable, no sequence
  (note 02 §1).

## 6. Open questions

- Transport: stdin / stdout JSON lines are simple and need no port. Large results (scores for
  1M rows) are better as a binary frame, or written by the plugin to a temp table the backend
  reads. Measure.
- Should a plugin also be callable outside a call (a long-running server plugin, a watcher)? It
  would break principle 1.
- Batch size for plugin writes, shared with note 01 §8.
- Plugin dependencies that need a specific Python version: one `uv` interpreter per plugin, or
  one shared interpreter version?
