---
tags: [inventory, frontend]
zone: folders-sources
---
# 13 · Folders & file sources

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the Folders tool window (file sources, then their folder trees, used as a filter), adding local or IIIF sources, and the server filesystem explorer. It pairs with the backend `06 File sources and IIIF` note.

## Zone-level checks
- [ ] ⚠ **Case mismatch that breaks Linux builds.** Git tracks the folder as `src/components/foldertree/` (lowercase: `FolderList.vue`, plus the dead `FolderList2.vue`, `TagList.vue` and `TagNode.vue`). On disk and in `FolderPanel.vue` (`import FolderList from '@/components/FolderTree/FolderList.vue'`) it's `FolderTree/`. macOS doesn't care (`core.ignorecase=true`), but a Linux/Docker/CI checkout creates `foldertree/` and the import fails. Commit `363e9690` "resolve lowercase uppercase mismatch" fixed the disk but not the git index. Fix: `git mv src/components/foldertree src/components/_tmp && git mv src/components/_tmp src/components/FolderTree`.
- [ ] ⚠ `FolderOptionDropdown.vue` and `FileSourceOptionDropdown.vue` both `import { i18n } from '@/main'`, which is a circular import. Use `@/locales/i18n`.
- [ ] `FileSourceOptionDropdown.vue` has `TODO: replace with a real API call once the backend exposes a connection-test endpoint`, so the connection test is fake.
- [ ] Folder filter: selecting a folder writes to `FilterManager.state.folders`. Check parent/child selection.
- [ ] `public/icons/iiif.svg` is the IIIF source icon. The unused `assets/images/IIIF-logo-colored-text.svg` duplicates it ([[99 Unused files]]).

## Files
- [ ] `src/components/layoutpanels/FolderPanel.vue` · 285 L. Folders tool-window root: the file sources, each with its folder tree, sync status and options.
- [ ] `src/components/FolderTree/FolderList.vue` · 195 L (git path `foldertree/`). Recursive folder tree with selection, image counts and options.
- [ ] `src/components/dropdowns/FolderOptionDropdown.vue` · 70 L. Per-folder menu (re-import, open in the file manager…). Changed on 2026-09-11.
- [ ] `src/components/dropdowns/FileSourceOptionDropdown.vue` · 123 L. Per-source menu: sync, connection test (TODO), remove.
- [ ] `src/components/modals/FileSourceModal.vue` · 524 L. Add a source: a local folder (through `FileExplorer`) or IIIF (manifest or collection, auth).
- [ ] `src/components/modals/FolderSelectionModal.vue` · 86 L. Pick a folder on the server (`FileExplorer`).
- [ ] `src/components/modals/FileExplorer.vue` · 334 L. Column-style browser of the server filesystem (`apiGetFilesystemLs`). Keeps the newest column in view.
- [ ] `src/components/filesystem/FolderItem.vue` · 84 L. One entry in an explorer column.
- [ ] `public/icons/iiif.svg`. IIIF icon, referenced as `/icons/iiif.svg` in `FolderPanel.vue`.
