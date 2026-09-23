---
tags: [inventory, frontend]
zone: home
---
# 14 · Home page, users & onboarding

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** route `/`. It covers the project list (create, open, import), user profiles, plugin management, detecting and converting old 0.x projects, the guided tour and the easter egg.

## Zone-level checks
- [ ] `HomeView.vue` handles the "classic update" case: no recent project but several old ones, in which case it proposes `LegacyImportModal`. Test it with and without legacy projects.
- [ ] `LegacyImportModal.vue` is written in French ("Propose de convertir…"). Check that all of its UI text goes through i18n.
- [ ] The user connect/disconnect flow (`UserSelector` → `panopticStore.connectUser`) works in multi-user (server) mode.
- [ ] The tour (`vue3-tour`) steps still point at existing elements after the June layout rework.

## Files
- [ ] `src/views/HomeView.vue` · 333 L. The home page: project list, `Create`, `Options`, `UserSelector`, plugins (`PluginForm`, `PluginOptionsDropdown`), `LegacyImportModal`, `Tutorial`, `Egg`.
- [ ] `src/components/home/Create.vue` · 90 L. Create-project form (name plus folder through `FolderSelectionModal`).
- [ ] `src/components/home/Options.vue` · 76 L. Home options.
- [ ] `src/components/home/UserSelector.vue` · 226 L. Pick, create, connect or disconnect a user profile.
- [ ] `src/components/modals/LegacyImportModal.vue` · 361 L. Proposes converting the old (0.x) projects that were detected. Drives the backend `legacy_migration.py`.
- [ ] `src/components/icons/PanopticIcon.vue` · 100 L. SVG logo (`HomeView`, `FirstModal`). It's the only live file in `icons/`.
- [ ] `src/tutorials/Tutorial.vue` · 324 L. Guided tour. Progress is kept in `localStorage`.
- [ ] `src/tutorials/Egg.vue` · 50 L. Easter egg (full-screen duck).
- [ ] `src/assets/duck.svg`. The duck image for `Egg.vue`.
