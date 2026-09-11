---
tags: [inventory, frontend]
zone: shared-ui
---
# 15 · Shared UI primitives, styling & i18n

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the building blocks every zone uses: the dropdown engine (`floating-vue`), tooltips, small layout utilities, the global theme, translations and `utils.ts`.

## Zone-level checks
- [ ] ⚠ `src/utils/utils.ts` line 10 has `import { Exception } from "sass"`, a stray editor auto-import. It's tree-shaken out of the build (no Sass code ends up in the bundle), but it's wrong. Remove it.
- [ ] `Dropdown.vue` has about 42 importers and `withToolTip.vue` (imported as `wTT`) about 41. Any change to them affects the whole app.
- [ ] `withToolTip.vue` shows only one tooltip at a time (module scope). Check this with nested tooltips.
- [ ] `theme.css` (755 L, "PyCharm Island Light") is the only global stylesheet, loaded by `App.vue`. The old `main.css` defines the same 58 class selectors and isn't loaded ([[99 Unused files]]).
- [ ] `fr.json` has 667 lines and `en.json` 636. Run `python scripts/check_locales.py` from the repo root (it needs `deepdiff`) to list missing keys.
- [ ] `utils.ts` (676 L, about 64 importers) mixes tree helpers, colour helpers (`chroma-js`) and navigation (`goNext`). Split it if it keeps growing.

## Files: dropdowns & tooltips
- [ ] `src/components/dropdowns/Dropdown.vue` · 146 L. Generic popper dropdown (`floating-vue`): width tracking, teleport, close-on-outside-click.
- [ ] `src/components/dropdowns/SelectDropdown.vue` · 176 L. Select-style dropdown with an icon-only mode (`VectorTypeDropdown`, `TextSearchInput`, `PointMapSelection`).
- [ ] `src/components/tooltips/withToolTip.vue` · 220 L. Tooltip wrapper, with one tooltip on screen at a time.

## Files: small utilities
- [ ] `src/components/utils/Collapsable.vue` · 75 L. Collapsible section (`NotifBody`).
- [ ] `src/components/utils/SectionDivider.vue` · 17 L. Titled divider (settings pages, `ActionSelectFlat`).
- [ ] `src/components/utils/Autofocus.vue` · 20 L. Focuses its child on mount (the action buttons).
- [ ] `src/components/inputs/RangeInput.vue` · 144 L. Custom slider (`ViewPanel` image size, map `Toolbar`, `SelectionModal`, `Similarity`).
- [ ] `src/components/loading/LoadWheel.vue` · 17 L. Spinner. It's the only live file left in `loading/`.
- [ ] `src/utils/utils.ts` · 676 L. Shared helpers: ids, folder and tag tree helpers, computed property values, colours, `arrayEqual`, `sleep`, `goNext`…

## Files: styling
- [ ] `src/assets/theme.css` · 755 L. Global theme tokens and utility classes.

## Files: i18n
- [ ] `src/locales/i18n.js` · 16 L. Creates the `vue-i18n` instance and exports `i18n` and `t`, so stores and builders can translate too.
- [ ] `src/locales/conf.js` · 7 L. Message map (`en`, `fr`).
- [ ] `src/locales/en.json` · 636 L. Changed on 2026-09-11.
- [ ] `src/locales/fr.json` · 667 L. Changed on 2026-09-11.
- [ ] `/scripts/check_locales.py` (repo root) · 74 L. Diffs the en/fr key sets with `deepdiff`.
