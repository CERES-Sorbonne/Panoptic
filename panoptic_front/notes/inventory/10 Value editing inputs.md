---
tags: [inventory, frontend]
zone: value-inputs
---
# 10 · Value editing inputs (cell, row, tree) & bulk edit

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** every editor for a property value, split into four families:
- **base inputs** in `property_inputs/`
- **cell inputs** for the grid, filters and stamp, in `property_cell_input/`
- **row inputs** for filters, stamp and grid, in `property_row_input/`
- **tree-cell inputs** for the mosaic and cluster cards, in `scrollers/tree/Tree*Input.vue` with `cellPopup`

Plus read-only previews, the DB binding wrapper, and bulk editing (stamp).

## Zone-level checks
- [ ] ⚠ There are three families for the same job (cell, row, tree). Check that each `PropertyType` behaves the same in all three: text, url, number, date, color, checkbox, tag and multi-tag.
- [ ] `DateInput.vue` (615 L) is the biggest input. Check the date formats and timezone handling.
- [ ] `IconTextInput.vue` caps how wide its expanded popup can grow. Check with long text or URLs.
- [ ] `cellPopup.css` is global, not scoped, because the popup is teleported. Check that the class names can't collide with anything else.
- [ ] Editing is kept out of text fields for undo: `App.vue` doesn't take over Ctrl+Z inside inputs.
- [ ] Read-only system properties (the backend refuses to write them) must render as `TreeValueRow` / non-editable everywhere.

## Files: base inputs (`property_inputs/`)
- [ ] `src/components/property_inputs/DBInput.vue` · 64 L. Wrapper that connects any property input to a value in the database (`GridPropInput`, `TreePropertyInput`).
- [ ] `src/components/property_inputs/TextInput.vue` · 169 L. Multi-line text editor built on `ContentEditable`. Used by 6 components.
- [ ] `src/components/property_inputs/ContentEditable.vue` · 176 L. `contenteditable` wrapper: plain-text paste, number-only mode.
- [ ] `src/components/property_inputs/IconTextInput.vue` · 334 L. Text input with a type icon and an expanding popup (`RowTextInput`).
- [ ] `src/components/property_inputs/NumberInput.vue` · 92 L
- [ ] `src/components/property_inputs/DateInput.vue` · 615 L. Segmented date input (number of slots per precision).
- [ ] `src/components/property_inputs/ColorInput.vue` · 78 L. Palette picker (`vue-color-kit`).
- [ ] `src/components/property_inputs/CheckboxInput.vue` · 44 L
- [ ] `src/components/property_inputs/TagInput.vue` · 128 L. Base tag picker (the duplicate of `tags/TagInput.vue`, see [[09 Properties and tags management]]).

## Files: cell inputs (`property_cell_input/`)
- [ ] `src/components/property_cell_input/CellTextInput.vue` · 89 L
- [ ] `src/components/property_cell_input/CellUrlInput.vue` · 90 L
- [ ] `src/components/property_cell_input/CellColorInput.vue` · 130 L
- [ ] `src/components/property_cell_input/CellTagInput.vue` · 145 L. Tags in a dropdown.

## Files: row inputs (`property_row_input/`)
- [ ] `src/components/property_row_input/RowTextInput.vue` · 46 L. The type icon shown inside the input (defaults to text).
- [ ] `src/components/property_row_input/RowUrlInput.vue` · 106 L
- [ ] `src/components/property_row_input/RowNumberInput.vue` · 60 L
- [ ] `src/components/property_row_input/RowDateInput.vue` · 69 L

## Files: previews (`property_preview/`)
- [ ] `src/components/property_preview/TextPreview.vue` · 22 L
- [ ] `src/components/property_preview/UrlPreview.vue` · 41 L
- [ ] `src/components/property_preview/NumberPreview.vue` · 23 L
- [ ] `src/components/property_preview/DatePreview.vue` · 53 L

## Files: tree-cell inputs (`scrollers/tree/`)
- [ ] `src/components/scrollers/tree/TreePropertyInput.vue` · 130 L. Dispatcher for one property row of a tree cell. It reports hover and focus to `hoverStore` / `inputStore`.
- [ ] `src/components/scrollers/tree/TreeCellFrame.vue` · 163 L. The box every tree-cell row lives in: property icon, then the value.
- [ ] `src/components/scrollers/tree/TreeTextInput.vue` · 191 L. Text and URL: shows the value, and becomes a real editor on click (popup).
- [ ] `src/components/scrollers/tree/TreeNumberInput.vue` · 103 L
- [ ] `src/components/scrollers/tree/TreeDateInput.vue` · 77 L. Formatted value, with the shared `DateInput` in a popup.
- [ ] `src/components/scrollers/tree/TreeColorInput.vue` · 129 L. Colour chip, with the palette in a popup.
- [ ] `src/components/scrollers/tree/TreeCheckboxInput.vue` · 51 L. The box itself is the value; there's no edit mode.
- [ ] `src/components/scrollers/tree/TreeTagInput.vue` · 192 L. Tag row, with the shared tag picker in a popup.
- [ ] `src/components/scrollers/tree/TreeValueRow.vue` · 56 L. Non-editable row: computed properties, `_folders`, and unsupported types.
- [ ] `src/components/scrollers/tree/cellPopup.ts` · 186 L. `useCellPopup`: placement of the teleported editors that are bigger than the 26 px row.
- [ ] `src/components/scrollers/tree/cellPopup.css` · 39 L. Global styles for those popups.

## Files: tables & bulk edit
- [ ] `src/components/inputs/PropertyInputTable.vue` · 107 L. Table of property editors for one image (`ImageProperties` in the image modal).
- [ ] `src/components/selection/SelectionStamp.vue` · 156 L. The "stamp" button for the current selection: set values on all selected images. It's in the top bar and the image modal, and was fixed on 2026-09-11.
- [ ] `src/components/inputs/StampDropdown.vue` · 124 L. Dropdown that hosts `StampForm`. Also used on tree group lines.
- [ ] `src/components/forms/StampForm.vue` · 228 L. Choose properties and values to apply to many images.
