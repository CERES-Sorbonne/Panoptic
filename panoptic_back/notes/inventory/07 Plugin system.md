---
tags: [inventory, backend]
zone: plugins
---
# 07 · Plugin system

Back to [[00 Backend inventory]] · Unused files: [[99 Unused files]]

**Scope:** installing, loading, hot-reloading and calling plugins (PanopticML, deepfaune…), and the API surface plugins are allowed to touch. The docs are `notes/plugin_architecture.md`, `notes/plugin_tutorial.md` and `/PluginSimpleGuide.md`.

## Zone-level checks
- [ ] **External contract.** Nothing in this repo imports `plugin.py`, but the plugins do. These are the modules the plugins in `~/PanopticML` and `~/deepfaune-panoptic-plugin` import, and renaming or moving any of them breaks those plugins:
  - `panoptic.core.plugin.plugin` (`APlugin`)
  - `panoptic.core.databases.media.models`
  - `panoptic.models.models`
  - `panoptic.models.action_models`
  - `panoptic.core.task.task`
  - `panoptic.core.databases.entity_schema`
  - `panoptic.core.databases.data.models`
- [ ] `notes/plugin_tutorial.md` still shows `from panoptic2.core.plugin.plugin import APlugin`, the old package name. `/PluginSimpleGuide.md` uses the correct `panoptic.core.plugin.plugin`.
- [ ] `plugin_installer.py` downloads zips from GitHub, GitLab or Bitbucket and runs pip on the plugin's own `requirements.txt`. Check error reporting when pip fails.
- [ ] Hot reload (`plugin_watcher.py`) is only active with `PANOPTIC_WATCH_PLUGINS=1`.

## Files
- [ ] `panoptic/core/plugin/__init__.py` · package marker
- [ ] `panoptic/core/plugin/plugin.py` · 102 L. `APlugin`, the base class every plugin subclasses (params, registered functions, `data_path`). **Only plugins import it**, so it must not be deleted.
- [ ] `panoptic/core/plugin/plugin_interface.py` · 275 L. `PluginProjectInterface`: the only project access a plugin gets (reads, writes, tasks, media).
- [ ] `panoptic/core/plugin/action_registry.py` · 140 L. `ActionRegistry`: introspects plugin functions and their docstrings into `FunctionDescription` / `ParamDescription`, and dispatches calls.
- [ ] `panoptic/core/plugin/load_plugin_task.py` · 86 L. `LoadPluginTask`: imports a plugin by module path (`importlib.import_module`) or by file (`spec_from_file_location`) and starts it at project load.
- [ ] `panoptic/core/plugin/plugin_installer.py` · 127 L. `PluginInstaller`: installs from a git host zip or a local dir, then pip-installs its requirements (uses `requests`).
- [ ] `panoptic/core/plugin/plugin_watcher.py` · 100 L. `PluginWatcher`: watches plugin sources with `watchfiles`, clears the module cache and reloads.
- [ ] `panoptic/models/action_models.py` · 130 L. `PropertyId`, `OwnVectorType`, `InputFile`, `ParamDescription`, `FunctionDescription`, `ActionContext`, `ScoreList`, `Score`… Shared with the frontend `actionStore.ts` / `models.ts`.
