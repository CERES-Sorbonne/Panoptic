---
tags: [inventory, frontend]
zone: actions-settings
---
# 12 · Actions, plugins & settings

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** running plugin functions ("actions") from the UI (buttons, default-function pickers, parameter inputs), the project settings modal (images, vectors, data, plugins) and installing plugins from the home page. It pairs with the backend `07 Plugin system` note.

## Zone-level checks
- [ ] ⚠ **Two generations of action button, both used:** `ActionButton.vue`, used by `tree/GroupLine` and `VectorSettings`, and `ActionButton2.vue` (hand-off mode: emits `submit` instead of awaiting), used by 7 components. Pick one.
- [ ] `ParamInputRow.vue` imports `@/data/actionStore.js` with a `.js` extension, unlike every other import.
- [ ] Param types coming from the backend (`action_models.py` → `ParamDescription`) are all handled by `ParamInput` / `ParamInputRow`, including the vector type (`VectorTypeDropdown`).
- [ ] Plugin install errors (backend `PluginInstaller`, pip failures) are surfaced in `PluginForm`.
- [ ] Earlier versions of these components are dead: `ActionSelect2`, `ActionSelectButton`, `PluginSettings2`, `GeneralSettings`, `ActionSettings` and `TabMenu` ([[99 Unused files]]).

## Files: actions
- [ ] `src/components/actions/ActionButton2.vue` · 238 L. Action button in hand-off mode: picks the function, edits params, emits `submit`. Used by reco, map, map toolbar, similarity and 3 others.
- [ ] `src/components/actions/ActionButton.vue` · 227 L. Older action button that awaits the run itself (`tree/GroupLine`, `VectorSettings`).
- [ ] `src/components/actions/ActionSelect.vue` · 126 L. Default-function selector for an action slot (`VectorSettings`).
- [ ] `src/components/actions/ActionSelectFlat.vue` · 202 L. Flat, sectioned variant with inline params (`ParamInputRow`) (`VectorSettings`).
- [ ] `src/components/actions/FunctionButton.vue` · 49 L. Runs a plugin function offered by a notification (`NotifBody`).
- [ ] `src/components/inputs/ParamInput.vue` · 152 L. Input for one function parameter, by type. Used by the action buttons and selectors and by `InputOptions`.
- [ ] `src/components/inputs/ParamInputRow.vue` · 118 L. Row layout of `ParamInput` (`ActionSelectFlat`).
- [ ] `src/components/dropdowns/VectorTypeDropdown.vue` · 73 L. Vector-type parameter picker, optionally filtered by source.

## Files: settings modal
- [ ] `src/components/modals/SettingsModal.vue` · 114 L. Settings modal with its pages (`PageWindow`). Clears the browser cache when the image routes change.
- [ ] `src/components/settings/ImageSettings.vue` · 182 L. Image sizes and thumbnail settings.
- [ ] `src/components/settings/VectorSettings.vue` · 95 L. Vector types, default actions, compute vectors.
- [ ] `src/components/settings/ComputeVectorButton.vue` · 28 L. Starts vector computation.
- [ ] `src/components/settings/DataSettings.vue` · 133 L. Data maintenance, such as refreshing after a `db_update` delta.
- [ ] `src/components/settings/PluginSettingsWindow.vue` · 53 L. Per-plugin pages (`PageWindow`).
- [ ] `src/components/settings/PluginSettings.vue` · 102 L. One plugin's base params and per-function defaults.

## Files: plugins on the home page
- [ ] `src/components/forms/PluginForm.vue` · 175 L. Install a plugin from a git URL or a local path, with a spinner.
- [ ] `src/components/dropdowns/PluginOptionsDropdown.vue` · 74 L. Per-plugin menu on the home page.
