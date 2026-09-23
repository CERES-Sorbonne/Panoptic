---
tags: [inventory, frontend]
zone: properties-tags
---
# 09 · Properties & tags management

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the Properties tool window (property groups, visibility, order, options), creating properties, the tag modal (tag tree and columns, colours, merge, children) and the display atoms (`PropertyIcon`, `PropertyValue`, `TagBadge`). Editing *values* is in [[10 Value editing inputs]].

## Zone-level checks
- [ ] ⚠ **Two tag pickers, both used**, and both headed "Base Input to select tags":
  - `components/tags/TagInput.vue` (122 L), used by `TagChildSelectDropdown`
  - `components/property_inputs/TagInput.vue` (128 L), used by `CellTagInput` and `TreeTagInput`

  Consolidate them.
- [ ] `tagtree/TagBadge.vue` is the only live file left in `tagtree/`. `tagtree/TagNode.vue` and `tagtree/TagTree.vue` are dead ([[99 Unused files]]). Consider moving `TagBadge` into `tags/`.
- [ ] Tag hierarchy cycles are handled: `storeutils.buildTagTree` drops cyclic edges and `wouldCreateTagCycle` guards edits. `TagTree.vue` draws the resolved edges.
- [ ] Property drag-and-drop order (`vuedraggable` in `PropertyGroupPanel` / `PropertyGroup`) is persisted.
- [ ] Hovering a property anywhere lights up its row in `PropertyOptions` (`hoverStore`).

## Files: properties tool window
- [ ] `src/components/layoutpanels/PropertyPanel.vue` · 102 L. Properties tool-window root in the sidebar split (`IslandPanel`, `TabContainer`).
- [ ] `src/components/layoutpanels/PropertyGroupPanel.vue` · 35 L. Draggable list of property groups.
- [ ] `src/components/menu/PropertyGroup.vue` · 260 L. One property group: header (rename, delete) and draggable properties.
- [ ] `src/components/menu/PropertyOptions.vue` · 329 L. One property row: visibility, type icon, options menu (rename, delete, tag menu), hover highlight.
- [ ] `src/components/modals/PropertyModal.vue` · 103 L. Create a property: name, type, mode, group.
- [ ] `src/components/dropdowns/PropertyTypeDropdown.vue` · 40 L. Property type picker.
- [ ] `src/components/dropdowns/PropertyModeDropdown.vue` · 41 L. Property mode picker (per instance or per image).
- [ ] `src/components/properties/PropertyIcon.vue` · 26 L. Icon for a property type. Used in 15 places.
- [ ] `src/components/properties/PropertyValue.vue` · 126 L. Read-only formatted value of any type. Used by group lines, the table header and `GroupSelect`.

## Files: tags
- [ ] `src/components/modals/TagModal.vue` · 335 L. Tag management modal: the tree plus columns, and the selected tag's images.
- [ ] `src/components/tags/TagTree.vue` · 546 L. Tag hierarchy graph, drawn from the resolved (acyclic) edges.
- [ ] `src/components/tags/TagColumn.vue` · 314 L. Column-browser view of tags.
- [ ] `src/components/tags/TagMenu.vue` · 230 L. Tag menu: search, create, pick. Used by `PropertyOptions` and both `TagInput`s.
- [ ] `src/components/tags/TagListScroller.vue` · 137 L. Virtualised tag list inside `TagMenu`.
- [ ] `src/components/tags/TagInput.vue` · 122 L. Tag picker (see the duplicate warning above).
- [ ] `src/components/tags/EditableTag.vue` · 92 L. Tag chip with rename and colour (`ColorDropdown`).
- [ ] `src/components/tagtree/TagBadge.vue` · 98 L. Coloured tag chip (lightens or darkens the colour). Used in 12 places.
- [ ] `src/components/dropdowns/TagOptionsDropdown.vue` · 97 L. Per-tag menu: colour (`ColorInput`), rename, delete.
- [ ] `src/components/dropdowns/TagChildSelectDropdown.vue` · 71 L. Pick child or parent tags.
- [ ] `src/components/dropdowns/ColorDropdown.vue` · 38 L. Colour picker dropdown for a tag.
- [ ] `src/components/images/TagImagesPreview.vue` · 59 L. The selected tag's images in `TagModal`.
- [ ] `src/components/preview/ImagePreview.vue` · 49 L. Small `TreeScroller` of images, used by `TagImagesPreview`. It's the only live file left in `preview/`.
