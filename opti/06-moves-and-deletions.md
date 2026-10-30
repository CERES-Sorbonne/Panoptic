# 06: Moves and deletions

Status 2026-10-29: proposal. Describes the target behaviour only. Builds on
[03-sqlite-layout.md](03-sqlite-layout.md) (the schema, sequence, tombstones, `entity_log`),
[04-column-store.md](04-column-store.md) (slots, delta updates) and
[05-elements.md](05-elements.md) (images, files, instances). Costs marked "estimate" are
orders of magnitude, not measurements.

## 1. Scope and principles

Files on disk change behind the app's back: they move, get renamed, edited, copied, deleted,
or sit on a disk that is not plugged in. This note says how Panoptic notices it, what it
shows the user, and what it writes.

The model of note 05, with one change: instances store `image_id` directly (the first open
question of 05 §11, answered yes).

- **image**: identical bytes, known by hash. Dense id, never reused.
- **file**: a location (source + folder + name), with mtime and size. Points to one image.
- **instance**: a sample from a data import, keyed by the user. It stores `image_id` (the
  truth) and an optional `file_id` (a location hint). An instance can lose its file and keep
  its image.
- User values live on images and instances. Files carry system properties only.

Principles:

1. **Disk is observed, the db is decided.** A rescan records what it sees and reports it.
   Merging, relinking and removing are options the user picks.
2. **Observing never deletes values.** A file that is not found is *missing*, not gone. No
   image or instance value is removed because of a scan.
3. **File churn is cheap by design.** Values are not on files, so a wrong move match or a
   lost file id costs no user data. Only the file id itself (selections, the instance
   hint) is at stake.
4. **One decision per folder, not per file.** A renamed root of 100k files is one entry in
   the report and one relink.
5. **Every decision is one undoable commit.** Purging images is the only final step.

## 2. Events

| # | event on disk | what it should mean |
|---|---|---|
| E1 | file moved or renamed inside a source | seen as a new file plus a missing file. The user can match them |
| E2 | folder moved or renamed inside a source | seen as a new folder plus a missing folder. The user can relink |
| E3 | file moved to another source | the image gets a new location in the other source |
| E4 | file deleted | the location is gone. The image may still have other files |
| E5 | folder deleted | E4 for a whole subtree, shown as one item |
| E6 | content changed in place (edit, re-encode, EXIF written by another tool) | same location, new hash: the file now points to another image |
| E7 | duplicate copy added | a new file of a known image. It shows the image's values at once |
| E8 | duplicate copy removed | a file gone, its image still has other files |
| E9 | source root not found (disk unplugged, share down, root renamed or deleted) | the same as E5 for the root folder: it is *missing*. Panoptic cannot tell an unplugged disk from a deleted folder, and does not need to |
| E10 | source truly deleted | E5 for the whole source, but only after the user says so |
| E11 | file restored (back from the trash, disk replugged, folder moved back) | the missing file is present again, same file id |
| E12 | user deletes in the app | a decision, not an observation: no review needed |

## 3. Detection

There are two moments where Panoptic learns that the disk changed. Nothing else watches the
disk: no file watcher, no scan at project open.

1. **Manual rescan** of a source or a folder, in one of two modes (§3.2):
   - *Rescan folders*: checks that the known folders still exist. Fast, no file is listed.
   - *Rescan files*: the full check. Finds new, missing and changed files.
2. **Failed image read** (§3.4). Finds missing files and folders while the
   user works.

### 3.1 Signals

| signal | cost | role |
|---|---|---|
| walk + `stat` | local SSD ≈ 1 s per 100k files, network share 10–60 s (estimate) | lists what is on disk now |
| mtime + size | free with the `stat` | "unchanged" for nearly every file, so no rehash |
| hash of the bytes | reads the whole file: ≈ 10 min per 100k photos of 3 MB on an SSD (estimate) | the image identity. Only for new and changed files |
| failed read | free: it happens anyway when an image is served | the only signal between rescans (§3.4) |

Not used: file watchers (no passive detection), inodes (unstable on FAT and network shares,
reused by the OS) and volume ids. An unplugged disk and a deleted folder look the same on a
local filesystem, and they get the same answer: the folder is missing until it comes back or
is relinked.

### 3.2 The two rescans

| | *Rescan folders* | *Rescan files* |
|---|---|---|
| checks | each known folder still exists | every file: present, new, changed, missing |
| disk work | one `stat` per folder | walk + `stat` per file, hash of new and changed files |
| cost | milliseconds for thousands of folders | ≈ 1 s per 100k files, plus hashing (§3.1) |
| finds | missing folders (E5, E9, and E2 seen from the old side) | every observed event of §2 (E1–E9, E11) |
| misses | files inside folders that still exist, new folders, content changes | nothing |
| writes | missing marks on the folders not found (their files follow, §4) | new files, missing marks, changed files (§6.2) |
| report | missing folders, with *Relink folder* | §5.2 |

*Rescan folders* is the cheap check to run first, for instance after plugging a disk back
in or moving a tree. A folder found again clears its missing mark, so its files are present
again (E11) without being listed. Files marked missing one by one stay missing until a
*Rescan files*. *Rescan files* is the one to run when files themselves may have changed.

*Rescan files* of one source:

1. **Folders first.** Do *Rescan folders*. A missing folder (the root included) is marked
   missing. Its subfolders and files are missing through it: they are not walked or marked
   one by one.
2. **Walk.** For each image file: folder path relative to the root, name, size, mtime.
3. **Same path.** Join with the db files of the source by (folder, name).
   - same size and mtime: present. If it was missing, it is restored (E11).
   - different: rehash. Same hash: refresh size and mtime. New hash: *changed* (E6). The
     file points to the new image, and a `pending_changes` row keeps the old one until the
     user chooses (§5.3).
4. **New.** Seen files not in the db: hash them, insert them. A known hash is a new copy of an
   existing image (E7), and shows that image's values at once.
5. **Missing.** Db files not seen: mark them *missing* (E4). A folder that still exists but
   lost all its files is reported as one entry.
6. **Report.** The rescan ends with a report: new, missing, changed, per folder (§5.2).

There is no move detection. A renamed or moved file is a **new file plus a missing file**
(E1, E2, E3). This costs nothing in values: the new file is hashed, finds its image, and
shows its values. What is lost is only the old file id, and the work to hash and thumbnail
the new file. The report offers to undo that split (§5.2), but never on its own.

### 3.3 Edge cases

| case | what the rescan sees | what the user can do |
|---|---|---|
| file renamed in its folder | a new file and a missing file with the same image | *Match in folder* (§5.2) |
| folder renamed or moved | a missing folder and a new folder | *Relink folder* (§5.2) |
| source root moved, disk unplugged | the root folder is missing | *Relink source* (§5.2), or plug the disk back and *Rescan folders* |
| file moved out of every source | a missing file | keep it missing, or remove it |
| content edited vs replaced by another picture | same path, new hash: *changed* | choose whether values follow (§5.3) |
| a missing file whose image has another present file | a removed copy | nothing to do: no value is at risk |

### 3.4 Detection on failed reads

Between rescans, the only signal is a read that fails: the backend can't open a file to
serve its raw image (or to build a missing thumbnail). It then finds out how far the loss
goes by testing the parents, closest first:

1. **The file.** If its folder exists but the file doesn't, the file is *missing*.
2. **The folders.** Walk up the parents and `stat` each one until one exists. The highest
   missing folder is marked missing (E5, or E2 if it was moved): one row, and its files are
   missing through it. One failed read marks a whole folder, not one file per request.
   The source root is a folder like the others (E9).

Rules:

- **It only marks state, persistently.** It writes `files.status` or `folders.status`, with
  their `status_scan_id`, and a `scans` row with mode *failed read* (observed state, §6.3),
  never a decision. It doesn't pair moves or touch values.
- **It suggests a rescan.** The UI shows "*Holidays/2019* is missing. Rescan *Photos*?" A
  rescan is still the only thing that can find where it went.
- **It is cheap and bounded.** A few `stat` calls per failure, cached per folder for the
  session, so a grid of 200 missing thumbnails costs one walk up, not 200.
- **A read that works again clears the mark** (E11).
- **Thumbnails hide the loss.** The grid shows cached thumbnails, so a missing file is
  usually noticed only when the raw image is opened, or by the next rescan.

## 4. States

| level | state | stored or derived | meaning |
|---|---|---|---|
| folder | present / missing | stored (`folders.status`) | missing: not found by a rescan or a failed read. The root folder of a source too |
| file | present / missing | stored (`files.status`), or derived: a parent folder is missing | a missing folder is one row write, not one per file |
| image | has files / only missing files / no files | derived columns (`files`: present count, `missing files`) | an image with no file row and no instance is an *orphan* |
| instance | has file / no file | derived from `file_id` and the file state | its image is kept either way |

Missing is a normal, lasting state. It needs no answer. The grid keeps showing those rows
with their cached thumbnail.

## 5. UI workflow

### 5.1 Principle

A rescan **observes and reports, it does not reconcile.** It writes what it saw (new files,
missing marks, changed hashes) and shows a report. Everything that merges, relinks or removes
is an option the user picks. The cost of not picking is low: a missing file keeps its image
and its values, only access to the raw image is lost when no other copy exists.

### 5.2 The rescan report

One panel per rescan, grouped by folder and by kind:
"`2019/trip/` 3,200 missing", "`2019/Trip/` 3,200 new", "4 changed in `best/`". An entry
expands to its files, paged like the grid. No modal dialog, no prompt per file.

Options in the report:

- **Match in folder.** In each folder, a missing file and a new file with the same image are
  the same file renamed. The option merges them: the missing row takes the new name and
  becomes present, and the new row is dropped. The file id survives, with its selections,
  custom groups and instance hints. Offered per folder and for the whole report. Never
  applied by the rescan itself.
- **Relink folder.** A missing folder is pointed at its new place by the user. Files are
  matched by relative name, checked by hash on a sample, and applied as one folder update.
  The new folder found by the same rescan is merged into it.
- **Relink source.** The user points a source whose root is missing to its new root. One
  write: folder paths are stored relative to the root.
- **Remove missing.** Drops missing file rows. Their images keep their values (orphans, if
  nothing else points to them).
- **Changed files.** *Values follow the new content* or *treat as a new picture* (§5.3).
- **Keep as is.** A valid answer: missing stays missing.

Each option is one commit, undoable.

**In the grid.**

- Missing files keep their cached thumbnail, dimmed, with a "missing" badge. A file with no
  cached thumbnail shows a placeholder.
- The full-size viewer shows the thumbnail and a banner with *Relink…*.
- System columns usable in filters, sorts and groups: file `status` (present / missing),
  image `files` (present count) and `missing files`, instance `has file`.
- Editing values works on missing rows. Values are in the db, not in the file.
- Tasks that need the bytes (new thumbnail size, a plugin computing vectors) skip missing
  images and report them.

**Trash.** Orphan images (no file row, no instance) are the trash. They keep their values and
their thumbnail. An images view filtered on `files = 0`, `missing files = 0` and no instance
shows them, with *Relink…* and *Purge*. Purge is the only step that deletes values and derived data. It is explicit and
final (§6.6).

**Undo.** Every option applied from the report is one commit in the history. Undoing it
restores the rows. The disk has not changed, so the entries are back in the report.

### 5.3 What happens to values

| case | image values | instance values | instance `image_id` | derived data (thumbnails, vectors) |
|---|---|---|---|---|
| rename or move, not matched (new + missing) | shown on the new file at once | unchanged | unchanged | reused by hash, nothing computed |
| rename or move, matched or relinked | unchanged | unchanged | unchanged | unchanged |
| copy added | shown on the new file at once | n/a | unchanged | reused, nothing computed |
| copy removed, other copies left | unchanged | unchanged | unchanged. `file_id` re-pointed to another present file | unchanged |
| last file missing | kept | kept | kept | kept: the grid shows the cached thumbnail, dimmed |
| last file removed from project | kept, the image is an orphan (trash) if no instance | kept | kept | kept until purge |
| content changed, *values follow* | copied to the new image where it has none | kept | re-pointed to the new image | computed for the new image. Old ones stay with the old image |
| content changed, *new picture* | stay on the old image | kept | kept on the old image (`image_id` is the truth) | computed for the new image |
| image purged | deleted | n/a: purge only takes images with no instance | n/a | deleted |

Default for a content change: *values follow* when the old image has no other present file
(an edit or a re-encode of the one copy), *new picture* when it has (one copy of a duplicate
was edited, so it is now a different picture). The panel shows the default and the count of
values and instances involved.

Instance values are never touched by a file event. A file event can only change an
instance's `file_id` hint, and its `image_id` only through an accepted content change.

### 5.4 Deletes started in the app

| action | disk | db | review |
|---|---|---|---|
| *Remove from project* (files, folder) | untouched | files rows deleted; the path is added to `file_sources.excludes` so the next scan does not re-add it | none |
| *Move to trash* (local sources only) | moved to the OS trash | files rows deleted | none |
| *Remove source* | untouched | the source, its folders and files deleted | none |
| *Delete instance* | untouched | the instance and its values deleted, as any data edit | none |
| *Purge* (orphan images) | untouched | images, their values and derived data deleted | confirmation, final |

Images whose last file is removed become orphans, not deletions. A removal can never cost
values. Only *Purge* can.

## 6. DB side

### 6.1 What this note needs from the schema

The tables and columns are defined in [note 03 §3](03-sqlite-layout.md#3-proposed-schema). This
note relies on:

- **Folders as name + parent** under a source with `root_url`: a folder move, a *Relink
  folder* or a *Relink source* is one row write. `file_sources.excludes` holds the paths
  removed from the project.
- **`status` on `folders` and `files`** (0 present, 1 missing). A file is missing when its own
  status or any parent folder's is, so an unplugged disk is one row. The root folder of a
  source is a folder like the others.
- **Rows of missing files are kept.** They hold the link to the image, the last path for
  *Relink…*, and the file id that selections and instance hints use.
- **Scan results**: `files.status_scan_id` and `folders.status_scan_id` (who set the status),
  `files.added_scan_id` (who found the file), one `scans` row per rescan or failed-read check,
  and `pending_changes` for changed files awaiting a choice. With these the report can be
  rebuilt from the db at any time.
- **`instances.image_id`** (the truth) and **`instances.file_id`** (a hint), both indexed for
  re-pointing.
- **Images get no state column.** Orphan state and file counts are derived.
- **Tombstones**: `images` has its own `table_id`, since purge deletes image rows. One
  tombstone stands for the image and all its values.

### 6.2 Writes per event

Status writes (`status`, `status_scan_id`) are observed state: sequenced, no `entity_log`
(§6.3). Every rescan and failed-read check also writes one `scans` row.

| event | rows written | `entity_log` | tombstones |
|---|---|---|---|
| new file: E1–E3 new side, E7 copy added | `files` insert with `added_scan_id`; `images` insert if the hash is new | yes, in the scan commit | none |
| E1–E3 old side, E4 file not found | `files.status` = missing | no | none |
| E5, E9 folder not found | `folders.status` = missing (one row) | no | none |
| E11 restored | `files.status` or `folders.status` = present | no | none |
| same path, same hash, new size or mtime | `files` update: `size`, `mtime` | no | none |
| E6 content changed | `images` insert if the hash is new; `files` update in place: `image_id`, `size`, `mtime`; one `pending_changes` row with the old image | the `files` update: yes, in the scan commit | none |
| E6 choice, *values follow* | image values copied to the new image where it has none; `instances.image_id` re-pointed; `pending_changes.decision` | yes, except `decision` | none |
| E6 choice, *new picture* | `pending_changes.decision` | no | none |
| *Match in folder* | missing row updated in place (`name`, `status`); new row deleted | yes | `files` (the new row) |
| *Relink folder* | one `folders` update (`parent`, `name`, `status`); the new folder rows of the rescan and their files merged into it | yes | `files`, `folders` (merged rows) |
| *Relink source* | `file_sources.root_url`; the root folder's `status` | yes | none |
| *Remove missing*, *Remove from project* | `files` deleted; instance hints re-pointed or NULL; `file_sources.excludes` for *Remove from project* | yes | `files` |
| purge | `images` and their value rows deleted | no, and log rows that name them are dropped | `images` only (note 03 §3) |

A match or a relink keeps the old file id and drops the new one. The old id is the one that
selections, custom groups and instance hints hold. The new row only lived since the rescan.

### 6.3 Observed state vs decisions

- **Scan results are persistent.** Everything a rescan or a failed read finds is written to
  `data.db`: the missing flags on files and folders, the new files, the changed files waiting
  in `pending_changes`, and one `scans` row with the counts. A missing flag stays until a
  later scan or a successful read clears it, across restarts. The report can be rebuilt from
  the db at any time, and scripts and plugins see the same state as the UI.
- **Observed state** (`files.status`, `folders.status`, their `status_scan_id`, `scans`,
  `pending_changes`, a size and mtime refresh) is sequenced, so the engine and plugins see it,
  but it is not in `entity_log`. Undoing "the file was not found" means nothing: the next scan
  would write it again. `scans` and `pending_changes` are small and get no tombstones: a
  reader re-reads them whole when they have a row newer than its sequence (note 03 §3).
- **Decisions** are commits. The automatic part of a rescan (new files, and changed files
  pointed to their new image) is one commit. Each option applied from the report (matches,
  relinks, removals, *values follow*) is one commit.
- Commit `source` tells them apart (`scan`, `review`, `relink`), so the history can show and
  filter them.

### 6.4 Undo

- Undo disables the commit. The resolver re-inserts deleted `files` rows with their old ids
  and restores updated ones. `AUTOINCREMENT` never hands those ids out again, so they are
  free.
- A re-inserted id is the same row coming back, not a new one. The delta reader sees its
  tombstone, then its insert at a later sequence. Deletes apply before sets (note 03 §3), so
  the slot is alive again. This replaces the "id that comes back is new" rule of note 04
  §6.2, which only existed because ids could be reused.
- After undo, the disk still differs from the db, so the undone items are back in the report.
- Purge cuts undo: a commit that names a purged image can no longer be undone, and the
  history shows it as such.

### 6.5 Engine and delta readers

- **Moves** change file system columns only (`folder`, `name`). A folder move changes the
  folder tree, and the derived `path` column is recomputed for its subtree (note 04 §6.2). No
  image or instance column moves.
- **Missing** is a file `status` column, derived from the file's own status and its folders'.
  A missing folder (or root) is one row in the delta and one recompute of that column.
- **Content changes** update the file → image map for those files and, with *values
  follow*, the instance → image map and the copied image values. All in one catch-up, one
  version (note 04 §6.1).
- **Removals** leave dead slots. Ids are never reused, so a dead slot never comes back as
  something else. Selections and custom groups drop dead ids when next used.
- **Holes.** Dead slots still take a cell in every loaded column of their level. When the dead
  share of a level passes a threshold (say 25% of the max id), the store remaps ids to dense
  slots at its next full reload. The map lives in memory only. Ids on disk never change, since
  plugins and `entity_log` refer to them.
- **Purge** writes one tombstone per image, not one per value (note 03 §3). A reader that sees
  a dead image drops all its cells. This keeps a purge of 100k images with 20 properties at 100k tombstone
  rows instead of 2M.
- `pending_changes` is not read by the engine.

### 6.6 Garbage collection and derived data

- **Nothing is collected while referenced.** An image is kept while a file row (present or
  missing) or an instance points to it.
- **Orphans keep everything** (values, thumbnail, vectors) until purged. The cached
  thumbnail is what the trash and missing files show.
- **Purge** is explicit, from the trash. An optional project setting purges orphans that have
  no user values after N days. Orphans with values are never purged automatically.
- **Derived data** lives in the media db (thumbnails, vectors, atlas) and in plugin stores,
  keyed by image id. It is a separate file, so its cleanup cannot share the data commit. Purge
  commits the data side first, then deletes media rows for the purged ids. A leftover row is
  harmless and a later pass deletes media rows whose image id no longer exists.
- **Plugins** learn about purges from the `images` tombstones in their delta read, and clean
  their own stores the same way.
- **A content change** computes derived data for the new image as for any new image. The old
  image keeps its own until it is purged.

## 7. Recommendation

1. **Observe and report (§5).** A rescan inserts new files, marks missing ones and lists
   changed ones, then shows a report grouped by folder. Matching, relinking and removing are
   options, each one undoable commit. Nothing is merged automatically.
2. **Missing is a state, not an error.** Keep the file row, the image and every value. Show
   the cached thumbnail dimmed with a badge, and offer a filter. The user may never answer.
3. **Only missing, no offline.** An unplugged disk and a deleted folder look the same, so both
   are a missing folder: one row, never a deletion. Relinking a source or a folder is one
   write, because folder paths are relative names.
4. **Two moments of detection.** A manual rescan, either *Rescan folders* (folder existence
   only, milliseconds) or *Rescan files* (new, missing, changed), and a failed image
   read, which tests its parents and marks the missing file or folder (§3.4).
   No watcher, no scan at open.
5. **No move detection.** A rename is a new file plus a missing one. *Match in folder* (same
   image, same folder) and *Relink folder / source* are options in the report.
6. **Matches keep the old id.** A match or relink updates the old row and drops the new one.
   Removals are tombstoned and undoable. Ids are never reused, so an undone delete revives
   its slot.
7. **Orphan images are the trash.** Removing files never removes values. Purge is the only
   final step, explicit, and the only one that deletes derived data.
8. **Instances follow `image_id`.** File events only touch the `file_id` hint. `image_id`
   changes only when the user accepts *values follow* on a content change.

## 8. Open questions

- *Match in folder* only matches within one folder. Should it also offer matches across
  folders of the same source (a file moved, not renamed), with a confirmation?
- Should the hash ignore metadata (hash the pixels, or the bytes outside EXIF / XMP)? Tools
  that write tags into files make E6 common. It needs a decode per file, and two files with
  equal pixels but different metadata would become one image.
- *Values follow* copies values to the new image. Should it also leave a link ("edited from
  image X") so the history and plugins can follow the chain?
- Auto-purge of value-less orphans: on by default, and after how long? It also bounds how far
  back undo can reach.
- How many `scans` rows to keep: all of them, or the last N per source?
- Exclusions as a JSON list on the source, or a table, once users exclude thousands of paths?
