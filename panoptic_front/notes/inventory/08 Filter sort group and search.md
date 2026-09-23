---
tags: [inventory, frontend]
zone: filter-sort-group
---
# 08 · Filter, sort, group & search

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the per-view filter island (bind toggle, instance/image mode, text search, filter, group and sort), the filter tree editor, the group and sort forms, and the property pickers they use.

## Zone-level checks
- [ ] ⚠ **Two property pickers, both used:**
  - `components/dropdowns/PropertyDropdown.vue` (38 L), used by `GroupForm` and `SortForm`
  - `components/properties/PropertyDropdown.vue` (62 L), used by `FilterRow`, `TagImport`, `ParamInput` and `ParamInputRow`

  Consolidate them.
- [ ] Two `TextInput`s exist: `inputs/TextInput.vue` (the search box in `PropertySelection`) and `property_inputs/TextInput.vue` (value editing). The shared name is confusing.
- [ ] The auto-reload toggle is gone: `toggles/ToggleReload.vue` is unused and the collection's `autoReload` has no UI ([[99 Unused files]]).
- [ ] `FilterGroup.vue` / `FilterRow.vue` still have a commented `props.manager.update(true)`. Check that updates are triggered correctly.
- [ ] Text search: semantic vs plain modes (`InputOptions` → action params), and the loading spinner.

## Files: filter island
- [ ] `src/components/layoutpanels/FilterIsland.vue` · 48 L. Island wrapper for the current tab's filter row, in `views/MainView`.
- [ ] `src/components/layoutpanels/FilterPanel.vue` · 79 L. Per-view filter row: bind toggle, instance/image mode, text search, and the filter, group and sort entries.
- [ ] `src/components/layoutpanels/ImageInstanceDropdown.vue` · 82 L. Switches between instance mode and image (sha1) mode.
- [ ] `src/components/inputs/TextSearchInput.vue` · 194 L. Search box for the collection. It uses the per-view collection when provided, and offers text/semantic modes and a spinner.
- [ ] `src/components/actions/InputOptions.vue` · 81 L. Options popup of the text search (the params of the search action).

## Files: filter tree
- [ ] `src/components/forms/FilterForm.vue` · 40 L. Filter entry of the filter panel.
- [ ] `src/components/dropdowns/MainFilterDropdown.vue` · 112 L. The filter dropdown: search, the `FilterGroup` tree, and property shortcuts.
- [ ] `src/components/filter/FilterGroup.vue` · 106 L. Recursive AND/OR group of rows.
- [ ] `src/components/filter/FilterGroupOperator.vue` · 38 L. AND/OR switch.
- [ ] `src/components/filter/FilterRow.vue` · 51 L. One condition: property, operator, value.
- [ ] `src/components/filter/OperatorChoice.vue` · 57 L. Operator picker, based on `availableOperators` for the type.
- [ ] `src/components/filter/FilterValueInput.vue` · 52 L. Typed value editor for a condition (reuses the row and cell inputs).
- [ ] `src/components/filter/AddFilterBtn.vue` · 34 L. "Add filter" button plus property picker.

## Files: group & sort
- [ ] `src/components/forms/GroupForm.vue` · 118 L. Group-by list: add, remove and reorder properties, per-group options, sort of the groups.
- [ ] `src/components/dropdowns/GroupOptionDropdown.vue` · 68 L. Options for one group-by entry, such as the date unit.
- [ ] `src/components/dropdowns/TimeUnitDropdown.vue` · 43 L. Date bucket unit.
- [ ] `src/components/forms/SortForm.vue` · 94 L. Sort-by list: property and direction.

## Files: property pickers
- [ ] `src/components/dropdowns/PropertyDropdown.vue` · 38 L. Dropdown property picker (`GroupForm`, `SortForm`).
- [ ] `src/components/properties/PropertyDropdown.vue` · 62 L. The other property picker (`FilterRow`, `TagImport`, `ParamInput`, `ParamInputRow`).
- [ ] `src/components/inputs/PropertySelection.vue` · 159 L. Searchable property list inside both pickers and `AddFilterBtn`.
- [ ] `src/components/inputs/TextInput.vue` · 74 L. Plain text input used as the search field of `PropertySelection`.
