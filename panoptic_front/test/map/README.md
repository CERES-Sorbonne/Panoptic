# Map view suite

Headless tests over the pure parts of the map view (`src/mixins/mapview/GridLayout.ts`).

```sh
npm test            # runs this suite with test/group
npm run bench:grid  # quality metrics and timings, not run in CI
```

`build.mjs` bundles `suite.ts` and `bench.ts` with vite (only the `@/` alias needs resolving) into
`test/map/.build/` (git-ignored).

| path | what it is |
| --- | --- |
| `harness/data.ts` | seeded synthetic clouds: uniform, and UMAP-like blobs |
| `harness/metrics.ts` | validity check and quality metrics (k-NN preservation, Spearman of distances, foreign adjacency) |
| `specs/grid_validity.ts` | one distinct in-bounds cell per point, edge cases, determinism |
| `specs/grid_quality.ts` | the grid keeps the projection's neighbourhoods and cluster separation |
| `specs/grid_cache.ts` | per-map grid cache (`mapGrid`) and cell placement (`cellCenter`) |

Quality thresholds sit below what `bench:grid` measures today: tighten them when the layout improves.
