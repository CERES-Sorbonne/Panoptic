---
tags: [inventory, frontend]
zone: tooling
---
# 16 · Tooling, config & build

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** package manifest, Vite, TypeScript, env files, formatting, `public/`, and where the build goes.

## Zone-level checks
- [ ] ⚠ **`npm run lint` fails.** ESLint 10.4.0 says "couldn't find an eslint.config.(js|mjs|cjs) file", because the only config is the legacy `.eslintrc.cjs` ([[99 Unused files]]). Write a flat config or drop the lint script and its deps.
- [ ] ⚠ **The build writes straight into the backend.** `vite.config.mjs` → `build.outDir = '../panoptic_back/panoptic/html'` with `emptyOutDir: true`. The committed copy there is currently stale (backend note `10 Build packaging and distribution`).
- [ ] Vite warns about chunks over 500 KB: `MainView` ≈ 1.13 MB, `index` ≈ 745 KB, `three` ≈ 525 KB. Consider lazy-loading the heavy views (map, graph) inside `MainView`.
- [ ] `package.json` dependencies:
  - 10 packages are never imported ([[99 Unused files]]).
  - Runtime libraries sit in `devDependencies`: `pinia`, `@vueform/slider`, `@vueform/toggle`, `@anilkumarthakur/vue3-json-viewer`. That works because Vite bundles everything, but it's misleading.
  - `"vite": ">=4.1.5"` is unpinned and resolved to Vite 8.0.13 (rolldown).
- [ ] `npm run typecheck` (`vue-tsc --noEmit`) passes with exit 0 and no errors, but only for files reachable from the entry. Dead `.vue` files aren't included, so their broken imports stay hidden ([[99 Unused files]]).
- [ ] `sass` is still needed as a build tool because `tutorials/Tutorial.vue` uses `<style lang="scss">`. `sass-loader` isn't needed.
- [ ] `tsconfig.json`: `strict` is on, but `noImplicitAny` and `strictNullChecks` are off. `"jsx": "react-jsx"` and `outDir` are leftovers (`vue-tsc --noEmit` is the only TS use).
- [ ] `vite.config.mjs` declares `replaceFiles` and `// assetsInclude`, which are unused.
- [ ] `.env.production` sets `VITE_API_ROUTE=""`, so production uses the same origin as the backend. `.env.development` points at `http://localhost:8001` and has a commented LAN IP.

## Files
- [ ] `package.json`. Scripts (`dev`, `build`, `preview`, `typecheck` = `vue-tsc --noEmit`, `lint`) and dependencies.
- [ ] `package-lock.json`
- [ ] `vite.config.mjs`. Vue plugin, `@` → `src` alias, `outDir` into the backend, `server.fs.allow ['..']`, `__VUE_PROD_HYDRATION_MISMATCH_DETAILS__`.
- [ ] `tsconfig.json`. `@/*` paths, strictness flags.
- [ ] `.env.development`. `VITE_API_ROUTE=http://localhost:8001`
- [ ] `.env.production`. `VITE_API_ROUTE=""` (same origin)
- [ ] `.prettierrc.json`. `{}` (Prettier defaults)
- [ ] `public/favicon.ico`. Linked from `index.html`.
