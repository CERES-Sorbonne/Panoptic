# 02: Storage

Status 2026-11-06: proposal. The storage block of the Rust backend (README): the database files,
what each holds, and who reads and writes them. `data.db` has its own note,
[01-sqlite-layout.md](01-sqlite-layout.md); this note covers the other files and the rules
shared by all of them. Sources: today's formats (`panoptic_back/panoptic/core/databases/media`,
`project`, `panoptic`).

## 1. Files

| file | where | holds | written by | read by |
|---|---|---|---|---|
| `data.db` | project folder | the annotated data: images, files, instances, subimages, values, history (note 01) | backend, plugins | engine, backend, plugins, scripts |
| `media.db` | project folder | derived data: thumbnails, vectors, atlas descriptions, maps (§2) | backend tasks, plugins | web server, engine (maps), plugins |
| `project.db` | project folder | the project's UI and settings: tabs, user defaults, plugin data, config (§3) | backend, plugins (their own data) | backend, plugins |
| `panoptic.db` | `~/.panoptic` | the install: users, known projects, installed plugins (§4) | backend | backend |
| `atlas/*.png` | project folder | atlas sheets, plain image files | backend tasks | web server |

All files are SQLite in WAL mode with `synchronous=NORMAL`. Ids come from `AUTOINCREMENT` in
the table that owns them (today's `id_registry` in `project.db` is gone): every id is then
allocated in the same file and transaction as its row, by whichever writer inserts it.

Only `data.db` has a sequence, history and tombstones (note 01 §7). The other files hold
derived data or UI state: they are not undoable, and their changes reach the clients through
events of the web server (note 08 §4), not through a change feed.

## 2. media.db

Everything in it can be rebuilt from the image files and the plugins, so losing it costs time,
not data. It is keyed by `data.db` ids: an image id or a subimage id (never reused, note 01 §3).

```sql
CREATE TABLE image_types (               -- thumbnail sizes
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,                    -- purpose: 'small', 'large', 'preview'
  format TEXT NOT NULL,                  -- 'jpeg' | 'webp' | 'png'
  width INTEGER, height INTEGER,         -- max size in px. NULL: no constraint
  auto_gen INTEGER NOT NULL              -- 1: generated at import; 0: on explicit request
) STRICT;

CREATE TABLE thumbnails (
  type_id  INTEGER NOT NULL,             -- → image_types.id
  image_id INTEGER NOT NULL,             -- → data.db images.id
  data BLOB NOT NULL,                    -- the encoded image
  PRIMARY KEY (type_id, image_id)
) STRICT;                                -- rowid table: rows are KBs, too large for WITHOUT ROWID

CREATE TABLE vector_types (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,                  -- the plugin that computes them
  params TEXT NOT NULL                   -- JSON: model and its parameters
) STRICT;

CREATE TABLE vectors (
  type_id  INTEGER NOT NULL,             -- → vector_types.id
  image_id INTEGER NOT NULL,             -- → data.db images.id
  data BLOB NOT NULL,                    -- float32 little-endian, the type's dimension
  PRIMARY KEY (type_id, image_id)
) STRICT;

CREATE TABLE subimage_vectors (
  type_id INTEGER NOT NULL,              -- → vector_types.id
  subimage_id INTEGER NOT NULL,              -- → data.db subimages.id
  data BLOB NOT NULL,
  PRIMARY KEY (type_id, subimage_id)
) STRICT;

CREATE TABLE atlases (                   -- thumbnail sheets for the map view
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sheet_count INTEGER NOT NULL,          -- files atlas/<id>_<n>.png
  width INTEGER NOT NULL, height INTEGER NOT NULL,
  cell_width INTEGER NOT NULL, cell_height INTEGER NOT NULL
) STRICT;

CREATE TABLE atlas_cells (
  atlas_id INTEGER NOT NULL, image_id INTEGER NOT NULL,
  sheet INTEGER NOT NULL, cell INTEGER NOT NULL,
  PRIMARY KEY (atlas_id, image_id)
) STRICT, WITHOUT ROWID;

CREATE TABLE maps (                      -- 2D projections (UMAP, t-SNE…) shown by MapView
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,                  -- the plugin that computed it
  name TEXT NOT NULL, key TEXT NOT NULL,
  count INTEGER NOT NULL
) STRICT;

CREATE TABLE map_points (
  map_id INTEGER NOT NULL, image_id INTEGER NOT NULL,
  x REAL NOT NULL, y REAL NOT NULL,
  PRIMARY KEY (map_id, image_id)
) STRICT, WITHOUT ROWID;
```

- **Keys.** Image ids, not hex hashes: the same id space as `data.db`, integers in the key, and
  the engine joins map points to rows with no lookup. The API serves a thumbnail by
  (type, image id) (note 08 §2). Hashes are built from `images.hash` when a plugin needs one.
- **Atlas and maps as rows.** Today `image_atlas.sha1_mapping` and `maps.data` are JSON blobs.
  As rows, the map frame of note 07 §8 is one range read of `map_points`, and an outside reader
  needs no decoder (note 01 §1, goal 4).
- **Cleanup.** A purge deletes the media rows of the purged images and their subimages after the
  data commit (note 04 §6.6). A later pass deletes rows whose image or subimage is gone.
- **Missing thumbnails.** Tasks that need the bytes skip missing files (note 04 §5.2). Today's
  `project_flags.thumbnails_dirty` stays the marker that a backfill is due (§3).

## 3. project.db

UI state and settings of one project. Small tables, read and written whole, so values that only
the front interprets stay JSON.

```sql
CREATE TABLE project_config (key TEXT PRIMARY KEY, value TEXT) STRICT;   -- JSON: id, name, description
CREATE TABLE project_flags  (key TEXT PRIMARY KEY, value TEXT) STRICT;   -- JSON: thumbnails_dirty, ...

CREATE TABLE tabs (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  state TEXT NOT NULL,                   -- JSON TabState: views and collections (note 06 §3)
  selection TEXT                         -- JSON
) STRICT;

CREATE TABLE user_defaults (
  user_id TEXT NOT NULL, key TEXT NOT NULL,
  data TEXT,                             -- JSON
  PRIMARY KEY (user_id, key)
) STRICT;

CREATE TABLE plugin_data (               -- a plugin's own state in this project
  plugin TEXT NOT NULL,                  -- the plugin's name (panoptic.db plugins)
  key TEXT NOT NULL,
  data TEXT,                             -- JSON
  PRIMARY KEY (plugin, key)
) STRICT;
```

- The engine reads a collection's state from `tabs.state` when the collection opens (note 06
  §2). The front stays the owner of that JSON and writes it through the API.
- `plugin_data` is keyed by plugin name, not by a numeric id, so it survives a reinstall.
- Selection is per user session (note 07 §7.2); `tabs.selection` only restores it.

## 4. panoptic.db

The install-wide database in `~/.panoptic`, outside any project.

```sql
CREATE TABLE panoptic_config (key TEXT PRIMARY KEY, value TEXT) STRICT;  -- JSON
CREATE TABLE users (
  id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE,
  description TEXT, password_hash TEXT
) STRICT;
CREATE TABLE user_data (                 -- per user, shared by every project (file explorer history…)
  user_id TEXT NOT NULL, key TEXT NOT NULL, data TEXT,
  PRIMARY KEY (user_id, key)
) STRICT;
CREATE TABLE projects (
  id TEXT PRIMARY KEY, path TEXT NOT NULL, name TEXT NOT NULL,
  excluded_plugins TEXT                  -- JSON list of plugin names
) STRICT;
CREATE TABLE plugins (
  name TEXT PRIMARY KEY,
  install_path TEXT NOT NULL,            -- the plugin's folder and venv (note 09 §2)
  source_type TEXT NOT NULL, source_path TEXT NOT NULL,
  version TEXT,                          -- the installed version the description belongs to
  description TEXT                       -- JSON: functions, params, hooks (note 00 §8.3)
) STRICT;
```

Today's `legacy_migrations` table (0.x projects) is left out: migration is out of scope for now.

## 5. Access

- **Backend.** One write connection per file, used by one writer task, so the backend's own
  writes to a file never contend with each other. A pool of read connections per file: the
  engine loads columns on several at once (note 05 §5.2), and the web server reads thumbnails
  and settings on others. Reads and writes run on blocking threads, never on the async runtime.
- **Plugins** open `data.db`, `media.db` and `project.db` themselves, through the Python plugin
  API, while the backend runs one of their functions (note 09). They write `data.db` by the
  rules of note 01 §7, `media.db` rows they compute (vectors, maps), and their own
  `plugin_data`. `panoptic.db` is not theirs.
- **Locks.** SQLite has one writer per file. Every connection sets a `busy_timeout`, and
  every writer keeps its transactions short (note 01 §7, rule 6). A plugin writing vectors for
  100k images writes in batches.
- **Scripts** read any file with plain SQL. They should not write: a write to `data.db` that
  breaks note 01 §7 can be lost on the next undo.

## 6. Open questions

- Thumbnails in `media.db` or as files: a 1M-image project holds GBs of small blobs. SQLite
  serves them fast, but a backup copies one huge file. Files would make it a folder of 1M
  entries.
- Vector storage for 10M images: one `vectors` table, or one table per vector type so a type
  is dropped in one step?
- `tabs.state` stays JSON owned by the front. Should the engine's part (collection state) get
  typed columns, so the backend can validate it?
