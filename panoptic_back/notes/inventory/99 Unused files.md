---
tags: [inventory, backend, unused]
---
# 99 · Unused backend files (and stale repo-root files)

Back to [[00 Backend inventory]]

Every file here is tracked in git but **not used**: no entry point or test reaches it, nothing references it, or it is broken. Each entry gives:
- what it most likely did
- what replaced it, if anything
- a suggested action

Dates are `created → last touched` from git. Paths are relative to `panoptic_back/` unless they start with `/`.

---

## A. Dead code (no importer anywhere)

- [ ] `panoptic/core/databases/project/project_db_config_reader.py` · 20 L · `fa9f8798` 2026-05-14 "writing the new panoptic", never touched since.
  - **What it was:** `get_project_config(path)` opens a `project.db` read-only (`?mode=ro`) and returns its `ProjectConfig` without opening a full `ProjectDB`. That's useful for peeking at projects (name, uuid) without locking them, for example on the home page list.
  - **Replaced by:** nothing directly. `Panoptic` / `ProjectDB` open `project.db` themselves, and the migrator has its own `read_project_config()` in `panoptic/migration/writers/panoptic_db.py`.
  - **Action:** delete it, or wire it into the project listing if read-only peeking is wanted.

## B. Broken tests (fail at import, so they contribute nothing)

- [ ] `test/test_media_db.py` · 203 L · 2026-05-14.
  - **What it was:** unit tests for `MediaDB`: default image-type seeding, upsert and delete of image types, the `auto_gen` flag.
  - **Why it fails:** `from panoptic.core.databases.media.media_db import _DEFAULT_IMAGE_TYPES`. That name no longer exists anywhere in `panoptic/`.
  - **Replaced by:** nothing. No other dedicated test covers `MediaDB`.
  - **Action:** fix the import (find where default image types are seeded now). Worth keeping.
- [ ] `test/test_project.py` · 947 L · last edit 2026-08-01 "readonly + small fixes".
  - **What it was:** the big `Project` integration suite: create and load projects, import images, import CSV data in instance and image modes (twice, with empty and missing values), clean up empty clones.
  - **Why it fails:** it imports `PropertyType, Property, PropertyMode, InstanceProperty, DbCommit, Instance` from `panoptic.models`, which is now an empty package. `PropertyType`, `PropertyMode`, `Property` and `Instance` live in `panoptic/models/models.py` (and `core/databases/data/models.py`). `InstanceProperty` and `DbCommit` no longer exist anywhere.
  - **Replaced by:** partly `test/test_data_db.py` (data layer) and `test/test_panoptic2.py` (project lifecycle), but not the import flows.
  - **Action:** fix the imports and rewrite the parts that used `DbCommit` / `InstanceProperty` against `Commit` / `ChangeOp`. Worth keeping.
- [ ] `test/test_project_db.py` · 125 L · 2026-05-19.
  - **What it was:** `ProjectDB` tests: file and image-type id allocation, tab data cycles, registry persistence, uuid, user defaults and plugin data isolation.
  - **Why it fails:** `from panoptic.models import Tag`. `Tag` is in `panoptic/models/models.py` now.
  - **Action:** a one-line import fix. Worth keeping.

## C. Manual or dev tools that nothing runs

- [ ] `panoptic/migration/schema/regenerate.py` · 68 L.
  - **What it is:** a vendored upstream tool (`python3 -m migrator.schema.regenerate`) that refreshes `upstream.json` from the standalone migrator's `analysis/` folder, which isn't vendored.
  - **Replaced by:** n/a. It only works inside the upstream repo.
  - **Action:** keep. `scripts/sync_migrator.sh` re-copies the whole folder anyway ([[08 Legacy migration (vendored migrator)]]).
- [ ] Storage-layer benchmarks written during the multi-database rewrite. None are imported or run by anything:
  - [ ] `test/scripts/bench_dataclass.py` · 172 L · 2026-03-28 "WIP msgspec.Struct to replace dataclass". Dataclass vs msgspec Struct vs pure rows vs Arrow ADBC. Outcome: the codebase uses `msgspec.Struct`.
  - [ ] `test/scripts/bench_deletes.py` · 121 L · 2026-04-09. History deletes: chunked `IN` vs temp table vs `executemany`.
  - [ ] `test/scripts/bench_delete_multi_pk.py` · 111 L · 2026-04-09. Multi-column-PK deletes: `executemany` vs temp table.
  - [ ] `test/scripts/bench_getter.py` · 106 L · 2026-04-09. Bulk reads: `IN` clause vs individual selects vs temp table.
  - [ ] `test/scripts/bench_query_pk.py` · 86 L · 2026-04-13. sha1-keyed lookups: chunked `IN` vs temp-table join.
  - [ ] `test/scripts/bench_transcation.py` · 55 L · 2026-04-13. SQLite concurrent transaction test (the file name is misspelled).
  - [ ] `test/scripts/bench_sqlite.py` · 255 L · 2025-11-25. EAV vs materialised-view experiment for dynamic properties.
  - [ ] `test/scripts/bench_duck.py` · 242 L · 2025-11-25. The same experiment with DuckDB. Outcome: DuckDB wasn't adopted.
  - **Replaced by:** their conclusions now live in `entity_schema.py` / `data_reader.py`.
  - **Action:** move them to an `archive/` folder or delete them. Git keeps the history.
- [ ] `test/scripts/generate_images.py` · 56 L · 2024-09-20. Generated the `test/data/images/number_N.png` fixtures. It's a one-off, and the images are committed.
- [ ] `test/scripts/tmp.db` · 2025-11-25 "save wip". Output of a benchmark. `.gitignore` excludes `test/scripts/*.db`, but this file was committed anyway. **Action:** `git rm --cached`.

## D. Stale test data

- [ ] `test/data/import_invalid.csv` · 2025-02-27 "fix export modal + #365". Neither `conftest.py` nor any test references it (the other three `import*.csv` files are used). **Action:** add a test for invalid headers, or delete it.

## E. Stale files at the root of `panoptic_back/`

- [ ] `freeze.txt` · 2023-11-22. `pip freeze` output from the 0.x era (faiss, torch, fastapi 0.99…). **Replaced by:** `uv.lock`. **Action:** delete.
- [ ] `requirements.txt` · created 2023-05-16, last edit 2026-03-28. Lists the old ML stack (torch, transformers, faiss-cpu, scikit-learn, pytesseract…) and misses `watchfiles`/`click`/`httpx`. Nothing reads it: `plugin_installer.py` reads each *plugin's* own `requirements.txt`, not this one. **Replaced by:** `pyproject.toml` + `uv.lock`. **Action:** delete, or regenerate it from `pyproject.toml`.
- [ ] `build_commans.txt` · 2023-05-16. Nuitka commands to compile `main.py` into a standalone binary with `--include-data-dir=html=html`. **Replaced by:** PyPI package + uv launchers + Docker. **Action:** delete.
- [ ] `description.md` · 2023-05-16 → 2023-06-28. The old PyPI long description: `python setup.py install`, `python panoptic/main.py`, "Windows install (coming soon)". **Replaced by:** `readme = "../README.md"` in `pyproject.toml`. **Action:** delete.
- [ ] `data.csv` · 2026-06-05. An export sample (`local_path;sha1[sha1]`), the input for `/scripts/create_fake_data.py` and `test/export_to_import.py`. It's only used by hand when run from this folder. **Action:** move it next to the scripts or into `test/data/`, or delete it.
- [ ] `data_import.csv` · 2026-06-05. Import sample (`path;Label[text];Score[number];Category[tag];Keywords[multi_tags]`) for manual import testing. **Replaced by:** `test/data/import*.csv` (used by the tests) and `test/gen_import_csv.py`. **Action:** delete, or move to `test/data/`.
- [ ] `test_import.csv` · 2026-06-05. Same idea, keyed by `id`. **Action:** as above.
- [ ] `tsne_coords.json` · 2024-10-25 "making ml plugin a real plugin". t-SNE coordinates in the old image URL scheme (`localhost:8000/small/images/<sha1>.jpg`), left over from when the ML/t-SNE view lived in the core. **Replaced by:** maps stored in `media.db` (`Map`) and computed by PanopticML. **Action:** delete.
- [ ] `thunder-collection_Panoptic.json` · 2023-03-14 export. Thunder Client (VS Code) collection for the 2023 REST API. The routes have all changed since. **Replaced by:** FastAPI's own `/docs`. **Action:** delete.

## F. Stale repo-root files (outside `panoptic_back/`)

- [ ] `/tree.txt` · 2025-10-08. ASCII component tree rooted at `App → PanopticView → …`, which is the pre-June-2026 frontend. **Replaced by:** the frontend inventory in `panoptic_front/notes/inventory/`. **Action:** delete.
- [ ] `/program.prof` · 2025-02-13 "rebuild front". A cProfile dump (≈390 KB). **Action:** delete, and add `*.prof` to `.gitignore`.
- [ ] `/install/start_panoptic_linux_old.sh` · 379 L. The pre-uv Linux installer (venv, pip, desktop entry). Renamed to `_old` on 2025-12-17. **Replaced by:** `install/start_panoptic_linux.sh` (uv). **Action:** delete.
- [ ] `/install/panoptic.desktop` · 2024-11-21. `.desktop` entry that only `start_panoptic_linux_old.sh` installs. **Replaced by:** nothing, since the uv script doesn't install a desktop entry. **Action:** delete, or reuse it in the new script.
- [ ] `/install/pedro.png` · 2024-11-22 "🥚". Easter-egg icon used only by the old Linux script. **Action:** delete.
- [ ] `/install/panoptic.ico` · 2024-11-22. Icon used only by the old Linux script. The Windows launcher is built from its own `install/windows/panoptic.ico`. **Action:** delete.
- [ ] `/.github/workflows/build-base.yml` · 2023-11-03. Manual workflow that builds `…/Dockerfile-base`, a file that doesn't exist. The bases are now `docker/*/Dockerfile-panoptic-clip-base`. **Action:** point it at the right Dockerfile, or delete it.

## G. Unused copies inside the committed frontend build

- [ ] `panoptic/html/icons/clustering.svg`
- [ ] `panoptic/html/icons/network.svg`
- [ ] `panoptic/html/icons/network2_white.svg`
- [ ] `panoptic/html/icons/network_2.svg`
- [ ] `panoptic/html/icons/network_black.svg`

  These are copies of `panoptic_front/public/icons/*`, which nothing references (see the frontend unused list). They disappear once they're removed from `public/` and the frontend is rebuilt.

## H. Dependencies declared in `pyproject.toml` but never imported
Not files, but the same kind of cleanup:

- [ ] `aiofiles`
- [ ] `aiosqlite`
- [ ] `fastapi-camelcase`
- [ ] `pypika`
- [ ] `pendulum`
- [ ] `imagehash`
- [ ] `show-in-file-manager`

  These were all used by the 0.x backend. The rewrite uses sync `sqlite3` + msgspec, its own SQL generation (`entity_schema.py`), and no camelCase conversion.

  Also, the opposite problem: **add** `msgspec`, `click` and `httpx`, which are imported but not declared. See [[10 Build packaging and distribution]].
