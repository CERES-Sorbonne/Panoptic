---
tags: [inventory, frontend]
zone: modals
---
# 11 · Modals, notifications, import & export

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the modal shells, the image detail modal and its panels, the selection wall, CSV import and export, and notifications. The settings modal is in [[12 Actions plugins and settings]], the folder and file-source modals are in [[13 Folders and file sources]], and the property and tag modals are in [[09 Properties and tags management]].

## Zone-level checks
- [ ] ⚠ **Two modal shells, both used:** `Modal.vue` (only `FirstModal` uses it) and `Modal2.vue` (8 users). Move `FirstModal` over to `Modal2` and delete `Modal`.
- [ ] Modals are imported in `App.vue` *and* `views/MainView.vue`. Check for double mounting ([[01 App shell routing and layout]]).
- [ ] `ExportModal2.vue` (534 L): export options against the backend exporter. The "2" suffix is left over from a deleted v1.
- [ ] `import/TagImport.vue` contains a "Placeholder API import". Check whether that path is finished.
- [ ] `modals/image/Instances.vue` deliberately uses its own `GroupManager`, not shared with `Similarity`, to avoid async races. Keep that in mind when refactoring `core/`.

## Files: shells
- [ ] `src/components/modals/Modal2.vue` · 176 L. Current modal shell (`modalStore`, size, close).
- [ ] `src/components/modals/Modal.vue` · 147 L. Older shell. Only `FirstModal` uses it.
- [ ] `src/components/modals/FirstModal.vue` · 60 L. First-launch modal (logo, intro). Mounted by `App`, `HomeView` and `MainView`.
- [ ] `src/components/utils/PageWindow.vue` · 65 L. Left option list plus a page area, used by the settings, import and file-source modals and the plugin settings window. The list hides once a page is selected.

## Files: image modal
- [ ] `src/components/modals/ImageModal.vue` · 401 L. Image detail modal: display, properties, instances, similarity panels, stamp.
- [ ] `src/components/modals/image/PanelBox.vue` · 77 L. Panel chrome: title bar, close button, body.
- [ ] `src/components/modals/image/ImageDisplay.vue` · 79 L. The image, filling the space the open panels leave.
- [ ] `src/components/modals/image/ImageProperties.vue` · 96 L. Property editors for the image (`PropertyInputTable`).
- [ ] `src/components/modals/image/Instances.vue` · 59 L. Other instances of the same sha1 (a `GridScroller` with its own `GroupManager`).
- [ ] `src/components/modals/image/Similarity.vue` · 350 L. Similarity results: action button, score slider (`@vueform/slider`), `ImageScroller`.
- [ ] `src/components/modals/ImageZoomModal.vue` · 40 L. Full-size zoom (`zoomModal.ts`).
- [ ] `src/components/modals/SelectionModal.vue` · 50 L. Every selected image in a flat, virtualised wall.

## Files: import & export
- [ ] `src/components/modals/ImportModal.vue` · 70 L. Import modal with its pages (`PageWindow`).
- [ ] `src/components/import/DataImport.vue` · 321 L. CSV upload, column/type mapping, fusion mode, import call.
- [ ] `src/components/dropdowns/FusionModeDropdown.vue` · 40 L. How imported values merge with existing ones.
- [ ] `src/components/import/TagImport.vue` · 147 L. Tag import (contains the placeholder API import).
- [ ] `src/components/modals/ExportModal2.vue` · 534 L. Export modal: properties, image copy options, selection or filter scope. The count is computed once when it opens.

## Files: notifications
- [ ] `src/components/modals/NotifModal.vue` · 170 L. Notification list and detail. Its own lazy chunk in the build.
- [ ] `src/components/notif/NotifPreview.vue` · 31 L. One line in the list.
- [ ] `src/components/notif/NotifBody.vue` · 75 L. Detail view: JSON viewer (`vue3-json-viewer`), collapsible sections, function buttons.
- [ ] `src/components/notif/NotifIcon.vue` · 19 L. Level icon.
