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
