# 05: Images, files and instances

Status 2026-10-29: proposal. Describes the target model only. Panoptic manages images only.
Engine numbers come from a scratch microbench (1M rows, 8 threads). Builds on
[03-sqlite-layout.md](03-sqlite-layout.md) and [04-column-store.md](04-column-store.md).

## 1. Three things called "an image"

| level | what it is | identity | created by |
|---|---|---|---|
| **image** | the content: identical bytes | hash of the bytes | the scan of a folder |
| **file** | a location: source + path | source + path | the scan of a folder |
| **instance** | one sample of the user's study | **a key given by the user** | a data import only |

Links only go up: instance → file (optional) → image. A file always has exactly one image. An
instance without a file reaches no image.

**Naming.** The third level is called **instance**, not element. Notes 01–04 and the API
already use "instance" for the row the engine filters, sorts and groups. The word also says
"one occurrence in the study", which fits a sample that can share its picture with other
samples. "Element" is vaguer and would add a rename.

## 2. Scenarios

The arguments below refer to these cases.

| # | scenario |
|---|---|
| S1 | The same photo is copied in two folders, `2023/cat.jpg` and `best/cat.jpg`. |
| S2 | A dataset has two samples whose images are byte-identical but carry different labels (a "cat" and a "dog" annotator, or the same picture in two tasks). |
| S3 | The user re-imports a corrected CSV that only knows file paths. |
| S4 | A scraped, noisy dataset: the same picture appears many times, sometimes with conflicting labels. The user wants to find and count the duplicates. |
| S5 | The user moves or renames a folder on disk, then rescans. |
| S6 | The user opens a folder of photos to browse and tag them. No data file at all. |
| S7 | A CSV row points to a file that is missing. |

## 3. Image vs file

### Why keep both

- **S1:** a tag or a note about the photo is set once and shows on both copies. A plugin
  result (embedding, thumbnail, OCR) is computed once per image, not once per copy.
- **S4:** "how many identical images" is the number of files per image. It needs a level
  where equal bytes are one thing.
- **S5:** after a move, the paths are new but the bytes are not. Values on the image survive
  with no re-linking.
- **S6:** the folder tree, the file name and the mtime are per location. Two copies in two
  folders are two entries in the tree.

### How to merge them

**(a) Files only.** The hash is a plain column of the file. "Same image" is a group by hash.
Values live on files.

**(b) Images only.** A row is a distinct image. Its paths are a list attribute. The file table
still exists on disk for the rescan, but files are not rows.

### Pros and cons

| | keep both | (a) files only | (b) images only |
|---|---|---|---|
| S1 tag once | yes | no: two copies can disagree, or every write fans out by hash | yes |
| S4 count duplicates | a derived image column | a group by hash, fine | `len(paths)`, fine |
| S5 move keeps values | yes, on the image | no: new paths are new files, re-link by hash, which rebuilds the image level | yes |
| S6 folder browsing | every file is a row | every file is a row | a copy in two folders is one row; folder filter is "any path in" |
| per-path system data (mtime, name) | on the file | on the file | a list per image, awkward to sort |
| compute per image (plugins) | once per image | once per file, or dedupe by hash by hand | once per image |
| levels, tables, id spaces | two | one | one row level, plus a sync table |
| "is this on the file or the image?" in the UI | must be answered (see §6) | never asked | never asked |

**Verdict.** (a) fails S1 and S5, which are everyday cases. (b) is honestly close to
workable for an image-only tool: the main loss is that a folder view can't show each copy as
its own tile. Keeping both costs little: the file table is needed for the rescan anyway, the
image table is a dictionary of hashes, and an extra row kind costs almost nothing in the
engine (§8). Keep both, with user values on the image only (§6).

## 4. File vs instance

### Why keep both

- **S2 (same path twice):** a CSV can list the same path in two rows with different labels.
  If an instance is a file, the second row overwrites the first.
- **S3:** with a user key, a re-import is an upsert by key. Same key: update. New key:
  create. Without a key, an instance level separate from files can't tell whether a row
  updates an existing instance or adds a new one, as soon as a file has more than one.
- **S5:** the user's key does not move with the folder. Re-importing the CSV with the new
  paths re-points the instances, and their values are kept.
- **S7:** a sample whose file is missing is still a sample. Its instance exists with no file.
- **External ids.** Datasets ship their own ids (`sample_0042`, a COCO image id). The key lets
  the user keep them, and export them back.

### How to merge them

**Instance = file.** The study row is the file, and its key is the path. A folder import
gives study rows directly.

### Pros and cons

| | keep both | merge (instance = file) |
|---|---|---|
| S2 same path twice | two instances | impossible |
| S3 re-import by path | upsert, if the key is the path | upsert by path, works |
| S5 move | values kept (key is stable) | sample values lost or re-linked by hash, which is ambiguous with duplicates |
| S7 missing file | an instance with no file | no row |
| external ids | kept as the key | only as a property, not as identity |
| S6 browse a folder | no instances needed, files are the rows | same |
| user effort | must choose a key that works for the whole project | none |
| row kinds in the UI | files and instances: two kinds of views | one |
| selection across views | converted between row kinds (§7) | nothing to convert |

**Verdict.** Keep both, but make instances optional. A plain folder import creates no
instances, so S6 costs nothing. A user whose data is keyed by path picks the path as key and
gets what the merge would give, while S2, S5, S7 and external ids stay possible.

### Instance identity

- **One key space per project.** There are no datasets. Every import writes into the same
  space. Choosing a key that works across all imports is the user's job: a project is one
  global overview, not a store of separate collections.
- **An import is an upsert by key.** No guessing from paths, no "first instance of this
  file".
- **An instance optionally points to one file.** The import resolves a path column to a file.
- **On disk** the key is `TEXT UNIQUE`, and the instance also has an integer id. Value tables
  and the engine use only the id. The key is read at import and export.

The cost is real: a user who picks a bad key (a file name that repeats across folders) gets
merged samples. The import must report keys that resolve to more than one file.

## 5. Image vs instance

### Why keep both

- **S2:** two samples, one picture, two labels. On an image level they collide: one label
  wins, or the import fails.
- **S4:** conflicting labels on duplicates are exactly what a noisy-dataset user wants to
  find. That needs both levels at once: labels on instances, and the image to see that they
  are the same picture ("images with more than one instance and more than one label").
- Image values (a tag "blurry", an embedding) still apply to every sample of that picture,
  with no copy per sample.

### How to merge them

**Instance = image.** A sample is a distinct picture. Labels go on images. A dataset import
writes image properties through the path.

### Pros and cons

| | keep both | merge (instance = image) |
|---|---|---|
| S2 equal bytes, different labels | two instances | impossible, one value wins |
| S4 conflicting duplicates | visible, filterable | hidden, or reported once at import and then lost |
| dedupe | piles by image over instances | built in: one row per picture |
| clean datasets with no duplicates | instances and images are 1:1, the level looks redundant | simpler |
| sample count | matches the dataset | lower than the dataset when it has duplicates, confusing for statistics |

**Verdict.** Keep both. This is the strongest of the three distinctions: merging silently
changes the user's data in S2 and S4. For clean datasets the merge is still available in
practice: import labels as image properties (§6), and no instances exist.

## 6. Properties

User properties live on **images** and on **instances**.

- **Image properties** say something about the picture, wherever it is: tags, notes, plugin
  results, width, height, EXIF. A value set from any row applies to every file and instance
  that reaches that image.
- **Instance properties** say something about one sample: labels, annotations, scores.

Files keep **system properties** only: path, folder, name, mtime.

### Are user file properties needed?

Three ways to handle a value that depends on the location:

1. **File properties.** A third user level, next to image and instance.
2. **Instances keyed by path.** The import creates one instance per path, and the value goes
   on it.
3. **Image properties through the path.** The import resolves path → file → image. If two
   paths with equal bytes get different values, the import reports the conflict and does not
   pick one. The user fixes the data, or re-imports with option 2.

| | file properties | no file properties (2 + 3) |
|---|---|---|
| a per-copy value typed by hand in a folder view | direct | not possible: the edit goes to the image, or the user imports instances first |
| S1 tag on one copy only | possible, but two copies of one photo then disagree for no visible reason | the tag reaches both copies, as expected for a photo |
| path-keyed CSV with equal-byte paths | written as is | a conflict report, then a choice |
| UI | every property asks "file, image or instance?" | "image or instance?", and instance only once a data import exists |
| storage, engine | two more value tables, a third level of columns | none |

**Verdict.** No user file properties. A value that really depends on the location is a
sample value, and option 2 covers it. The loss is a hand-typed per-copy value without an
import. It is rare for images, and folder-dependent facts (a `train` / `test` split by
folder) are already system columns.

## 7. What the user sees

The grid shows one kind of row per view, plus optional piles.

| view | rows | piles | typical use |
|---|---|---|---|
| folders | files | by image (optional) | browse, find copies |
| images | images | none | one tile per distinct picture |
| study | instances | by image or by file (optional) | work on imported data |

- Columns shown: the row's own level and the levels above it. Instance properties are not
  plain columns in a file or image view, since one file can have many instances.
- Editing an image property from any row changes it for every row that reaches that image.
  The UI says how many rows that touches.
- "How many identical images" is the number of files per image, a derived image column
  usable in filters, sorts and groups. "Instances per image" is another one.
- A study view shows instances only. Files that no instance points to are not shown.
- Selection and custom groups hold row ids tagged with their row kind. Switching the view
  converts them: down is exact (every file of a selected image), up must choose between "any"
  and "all".

## 8. Engine

One structure serves every row kind (image, file, instance), so operators are written once.

- **Columns are stored at their own level**, indexed by that level's id. Id 0 means "none" at
  every level, and cell 0 of every column is "no value", so a missing link reads as empty
  with no branch.
- **A row space** gives, for the chosen row kind, the map from each row to its image, and to
  its file for instances. The instance → image map is stored combined, so a read across two
  levels is one lookup. An image → rows index is built when a count or a pile needs it.
- **Reads only go up.** An operator reads a column directly when it is at the row's level, or
  through the map when it is above. A column from a lower level is not a plain column in a
  higher view. Aggregates (count, any of the tags, min / max) are derived columns stored at
  the upper level.
- **Per-column caches live at the column's level** and are shared by every row space: dense
  group codes, sort keys, date-step codes, expanded tag lists. They are the main speed lever.
- **No code per row kind.** No operator gained from separate code for image, file or
  instance rows. The only special cases: piles use an array indexed by image id, and image
  rows have no piles.

### Measured

Scratch microbench, 1M rows, 8 threads.

| operation | read directly | read through the map |
|---|---:|---:|
| filter | 0.06 ms | 0.15 ms |
| sort | 3.53 ms | 3.55 ms |

| group by a number column | time |
|---|---:|
| hashing each row's value | ≈ 10 ms |
| cached dense codes, file rows (1M) | 3 ms |
| cached dense codes, instance rows (3M) | 4 ms |

Piles: an array indexed by image id is 1.6–1.8× faster than a hash map.

The map costs under 0.1 ms on a filter and nothing measurable on a sort. The extra levels are
not a speed cost. Caching per column is what matters.

### Result tree

A result is a tree of groups whose leaves hold row ids in display order. A header says which
level the ids belong to (`row_kind`) and how leaves are piled (`pile_by`). The tree itself
does not depend on the level. Piles are a layout per leaf: a permutation of the leaf's rows
plus the pile bounds, with the image (or file) id of each pile.

## 9. Disk layout

Replaces the identity part of note 03 §3.

```sql
CREATE TABLE images (
  id   INTEGER PRIMARY KEY AUTOINCREMENT, -- never reused: the id is the engine slot
  hash BLOB NOT NULL UNIQUE,              -- first byte names the hash algorithm
  size INTEGER NOT NULL,
  sequence INTEGER NOT NULL
) STRICT;

CREATE TABLE files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  folder_id INTEGER NOT NULL,
  image_id  INTEGER NOT NULL,             -- → images.id
  name  TEXT NOT NULL,
  mtime INTEGER,                          -- unix ms
  sequence INTEGER NOT NULL
) STRICT;
CREATE INDEX files_image ON files(image_id);

CREATE TABLE instances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL UNIQUE,               -- the user's id
  file_id INTEGER,                        -- → files.id, optional
  sequence INTEGER NOT NULL
) STRICT;
CREATE INDEX instances_file ON instances(file_id);
```

- Value tables: `image_values`, `image_tag_values`, `instance_values`,
  `instance_tag_values`. Same shape as note 03: property first in the key, `WITHOUT ROWID`,
  a `sequence` index. No user value tables for files.
- `AUTOINCREMENT` keeps ids from being reused after a delete, so an id always denotes the
  same row and can be the engine slot directly. No id → slot table.
- Width, height and EXIF are image system properties stored as image values, not columns of
  `images`.
- The tombstone `table_id` list of note 03 follows: image, file and instance tables and
  their value tables.

## 10. Recommendation

Keep the three levels, with instances optional and no user file properties.

1. **Image vs instance: keep, firmly.** Merging loses data in S2 and hides the conflicts of
   S4, which is a main reason to use the tool on a dataset.
2. **File vs instance: keep, as an opt-in level.** A folder-only project never sees
   instances. A data import creates them, keyed by the user. That fixes re-imports (S3),
   survives moves (S5), allows missing files (S7) and keeps external ids. The price is that
   the user must choose a key, and the import must warn about keys that look ambiguous.
3. **Image vs file: keep, the weakest of the three.** "Images only" would nearly work.
   Files stay as rows because the folder view needs one tile per copy, the table exists
   anyway for the rescan, and the engine cost of a row kind is measured as negligible. If
   files as rows turn out to confuse users, dropping file rows is the cheapest of the three
   merges, since files carry no user values.
4. **User values on two levels only**, image and instance. This keeps the UI question to
   "about the picture, or about this sample?", and it is only asked once instances exist.

## 11. Open questions

- Should an instance be able to point to an image directly, with no file (a picture known by
  hash whose file is gone)? It would keep S5 and S7 instances attached to their image.
- When a rescan removes a file that instances point to, set `file_id` to null, or re-point
  to the image's other file when there is exactly one?
- Ids are never reused, so many deletes leave holes in the engine arrays. At what share of
  dead ids does the store remap?
- Key type: always text, or text plus an optional integer column for fast numeric keys?
- Should an import keyed by path warn when the chosen key is a bare file name that repeats
  across folders?
