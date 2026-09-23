---
tags: [inventory, frontend]
zone: folders-sources
---
# 13 · Folders & file sources

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the Folders tool window (file sources, then their folder trees, used as a filter), adding local or IIIF sources, and the server filesystem explorer. It pairs with the backend `06 File sources and IIIF` note.

## Zone-level checks
*Refreshed 2026-09-21.*

- [x] ~~**Case mismatch that breaks Linux builds.**~~ Resolved: git and disk now agree on
  `src/components/folder_tree/` (`FolderList2.vue`, `FolderRow.vue`, `TagList.vue`,
  `TagNode.vue`), and `FolderPanel.vue` imports that path.
- [x] ~~`FolderOptionDropdown.vue` / `FileSourceOptionDropdown.vue` import `i18n` from
  `@/main` (circular).~~ Resolved: nothing imports `@/main` any more.
- [ ] `FileSourceOptionDropdown.vue` has `TODO: replace with a real API call once the backend exposes a connection-test endpoint`, so the connection test is fake.
- [ ] Folder filter: selecting a folder writes to `FilterManager.state.folders`. Check parent/child selection.
- [ ] `public/icons/iiif.svg` is the IIIF source icon. The unused `assets/images/IIIF-logo-colored-text.svg` duplicates it ([[99 Unused files]]).

## Files
- [ ] `src/components/layoutpanels/FolderPanel.vue` · 311 L. Folders tool-window root: the file sources, each with its folder tree, sync status and options.
- [ ] `src/components/folder_tree/FolderList2.vue` · 205 L. Recursive folder tree with selection, image counts and options.
- [ ] `src/components/folder_tree/FolderRow.vue` · 175 L. One row of that tree: expand/collapse, selection state, count and the per-folder options menu.
- [ ] `src/components/folder_tree/TagList.vue` · 28 L + `TagNode.vue` · 88 L. The tag-tree variant of the same pattern (used by the tag/property side, not by the folder panel).
- [ ] `src/components/dropdowns/FolderOptionDropdown.vue` · 70 L. Per-folder menu (re-import, open in the file manager…). Changed on 2026-09-11.
- [ ] `src/components/dropdowns/FileSourceOptionDropdown.vue` · 123 L. Per-source menu: sync, connection test (TODO), remove.
- [ ] `src/components/modals/FileSourceModal.vue` · 524 L. Add a source: a local folder (through `FileExplorer`) or IIIF (manifest or collection, auth).
- [ ] `src/components/modals/FolderSelectionModal.vue` · 86 L. Pick a folder on the server (`FileExplorer`).
- [ ] `src/components/modals/FileExplorer.vue` · 334 L. Column-style browser of the server filesystem (`apiGetFilesystemLs`). Keeps the newest column in view.
- [ ] `src/components/filesystem/FolderItem.vue` · 84 L. One entry in an explorer column.
- [ ] `public/icons/iiif.svg`. IIIF icon, referenced as `/icons/iiif.svg` in `FolderPanel.vue`.
