> **Status 2026-09-21.** The map view was reworked in `6799e47f` "Map view integration",
> after these notes were written. What landed:
> - **P0/P1 — done.** `MapView.vue` takes `collection: GroupInspector` (the same surface as the
>   scrollers), reads selection through `collection.selectionNamespace` over `columnStore`'s
>   namespaced masks, gets `imageSize` from `ViewPanel`, and clusters through
>   `collection.cluster(leaf.id, req)`. The prop is called `collection`, not `manager`.
>   `MapMenu.vue`, `ImageMap.vue`, `MapRendererView.vue` and `ImagePreview.vue` were folded
>   into `MapView.vue` (722 L) + `Toolbar.vue` and no longer exist.
> - **Not built:** `src/core/group/frontier.ts`. P3's "visible frontier" is still one
>   implementation per view — `GroupView.vue` has its own `walkVisible`, and the map still
>   colours by root children. P2, P4 and P5 are likewise open.
>
> So: read `mapview_current_state.md` as the *pre-integration* snapshot, and the sync model /
> design / plan as the intent that is still only partly delivered.

# Map view — modernisation

`MapView.vue` predates the split-view / inspection rework (`notes/refactor/`). It still
works, but it is the last view that talks to the collection in the old dialect: it takes a
concrete `CollectionManager`, reaches into `filterManager.result`, reads exactly one level
of the group tree, and rebuilds its whole GPU state on every `version` tick.

These notes say what it does today, what "synchronised with the other views" has to mean
concretely, and how to get there.

Read in this order.

1. **`mapview_current_state.md`** — the functionality inventory (what would be lost if it
   were rewritten from scratch) plus the audit: where it disagrees with the current
   architecture, and the three real bugs that fall out of that.
2. **`mapview_sync_model.md`** — the core proposal. *The map is a projection of the same
   result tree, not a second tree.* Defines the **visible frontier** (the one concept the
   tree scroller, the group view and the map all need to share) and gives the per-aspect
   synchronisation contract.
3. **`mapview_modern_design.md`** — the component decomposition, prop contracts, the
   geometry/colouring split and its cost model, and the interactions the map should gain
   once it reads the real tree.
4. **`mapview_implementation_plan.md`** — phased, each phase shippable on its own, with the
   open decisions that need an answer before the phase that depends on them.

Architecture context lives in `notes/refactor/`: `collection_inspection_mission.md` (why
`CollectionManager` is the inspection object), `collection_pipeline_audit_fixes.md`
(§*Facade* — why the scrollers take a `GroupInspector`), and `cluster_view_goals.md` (the
grafted-cluster model the map's "cluster" colour mode is silently out of step with).
</content>
</invoke>
