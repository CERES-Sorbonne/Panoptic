---
tags: [inventory, backend]
---
# Backend inventory (`panoptic_back`)

Snapshot of branch `rework-front` @ `72e9faeb`, 2026-09-11.
Every file that is **used** is listed in exactly one zone note below, as a checkbox to tick once you've reviewed it by hand. Files that are **not used** are in [[99 Unused files]], each with what it used to do and what replaced it.

## How "used" was decided
- **Python.** I built a static import graph with Python's AST (absolute and relative imports, `from x import submodule`, literal `import_module`). A file counts as *runtime-used* if it's reachable from one of the entry points:
  - `panoptic.cli:cli` (the `panoptic` console script) → `panoptic/main.py`
  - `python -m panoptic.migration`
- **Tests.** Reachable from `test/test_*.py`, `test/conftest.py` or `panoptic/migration/tests/`. Checked with `pytest --collect-only`.
- **External users.** The plugins (`~/PanopticML`, `~/deepfaune-panoptic-plugin`) were grepped too. `core/plugin/plugin.py` is only imported by them, so it counts as used.
- **Non-Python files** (DBs, CSVs, SQL, images, config) were matched by name against code, config, Docker and CI files.
- **Limits.** This is static analysis, not coverage. A file can be reachable yet contain dead functions, and dead *routes* aren't detected. The only dynamic imports in the codebase are plugins (`load_plugin_task.py`).

## Numbers
| | files |
|---|---|
| Python files (tracked) | 126 |
| used at runtime | 97 (96 reachable + `plugin.py` for plugins) |
| test modules and support | 16. **3 of them fail at import** |
| manual scripts under `test/` | 11: 2 kept helpers, 9 in [[99 Unused files]] |
| unreachable code | 2, both in [[99 Unused files]] |
| committed frontend build (`panoptic/html/`) | 26 |

## Zone notes
| # | Zone | Covers |
|---|---|---|
| 1 | [[01 Entry point server and API]] | `cli.py`, `main.py`, Socket.IO server, DB watcher, routes, wire models |
| 2 | [[02 Panoptic home users and legacy discovery]] | `Panoptic`, `panoptic.db`, users, 0.x discovery |
| 3 | [[03 Project runtime tasks import export]] | `Project`, task queue and tasks, CSV importer/exporter |
| 4 | [[04 Data DB and versioning]] | `entity_schema` ORM, SQLite reader/writer, `data.db`, undo resolver |
| 5 | [[05 Media and project DBs]] | `media.db`, `project.db` |
| 6 | [[06 File sources and IIIF]] | local and IIIF readers, thumbnail processing |
| 7 | [[07 Plugin system]] | plugin base, interface, loader, installer, watcher, action models |
| 8 | [[08 Legacy migration (vendored migrator)]] | `panoptic/migration/**`, `sync_migrator.sh` |
| 9 | [[09 Tests and fixtures]] | pytest suite, migrator suite, fixtures, helpers |
| 10 | [[10 Build packaging and distribution]] | `pyproject`, `uv.lock`, `panoptic/html/`, Docker, installers, CI, repo-root docs |
| — | [[99 Unused files]] | dead code, broken tests, stale data, config and root files |

## Most important findings (all verified on 2026-09-11)
1. ⚠ **The package build is broken.** `panoptic/__init__.py` is empty, but it's the hatch version source, so `uv run`, `pip install .`, Docker and PyPI publish all fail. See [[10 Build packaging and distribution]].
2. ⚠ **Dependencies have drifted.** `msgspec`, `click` and `httpx` are imported but not declared. `aiofiles`, `aiosqlite`, `fastapi-camelcase`, `pypika`, `pendulum`, `imagehash` and `show-in-file-manager` are declared but never imported.
3. ⚠ **3 of the 15 pytest modules don't import** (`test_media_db`, `test_project`, `test_project_db`), and no CI job runs the tests.
4. ⚠ **The committed `panoptic/html/` build is stale** compared with the current frontend source, and it ships the dev routes `/test` and `/test-points`.
5. ⚠ `docker/gpu/Dockerfile-panoptic` has a `pip3 install --force-reinstall` with no package, and `.github/workflows/build-base.yml` points at a Dockerfile that doesn't exist.
6. The global exception handler returns full tracebacks to the client, including in `PANOPTIC_REMOTE` mode.
7. **Plugin contract.** Seven internal modules are imported by the external plugins, so renaming any of them breaks the plugins ([[07 Plugin system]]).
8. `routes/project_routes.py` is 1874 lines, the largest file in the backend.

## Not inventoried
`notes/` (this vault), `.venv/`, `.idea/`, `.pytest_cache/`, `__pycache__/`, and the repo-root tool folders `.claude/`, `.obsidian/`, `.opencode/`, `.panoptic2/`.
The frontend has its own inventory in `panoptic_front/notes/inventory/`.
