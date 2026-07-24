# sha1 piles — implementation task list

Ordered, do-one-at-a-time checklist. Background/rationale in
`sha1_mode_flat_piles_optimization.md`. Each task is independently committable and leaves
the app working.

**Goal:** replace per-sha1 child `Group`s with a non-destructive pile overlay
(flat instance array + boundary index) stored in a side map; scrollers render piles.

**Decisions locked:**
- No sub-groups. Leaf instances stay a flat array; piles are `order` + `bounds`.
- null sha1 → **throw** (never valid; sha1 written eagerly at instance creation).
- Pile data in a side map (`pileIndex`), never on the Group node → cluster recovered for
  free on revert.
- Pipeline order: `group → insert/update custom groups → apply sha1Mode` (sha1 is the
  final pass).
- Piling applies to **all** final leaves (property leaves and cluster leaves).
- Keep separate from backend `isSha1Group` cluster flag.

---

## Phase 1 — flat piles on current architecture (independent of cluster mission)

> **STATUS: implemented (T1–T10), `vite build` passes.** Runtime verification in the
> actual app (toggle sha1Mode, cluster + sha1, shift-select across piles, image modal
> from a pile, incremental update) still to be done by hand — no test runner in repo.

### T1. Pure pile module
- [ ] Create `src/core/sha1Piles.ts`.
- [ ] Define `interface PileData { order: number[]; bounds: number[] }`.
      `bounds` = first-index of each pile, with `order.length` appended as final sentinel,
      so pile `k` = `order[bounds[k] .. bounds[k+1]]`.
- [ ] `computeSha1Piles(slots: number[], sha1s: (string|null)[]): PileData | undefined`
      - Stable-bucket slots by `sha1s[slot]` in first-seen order.
      - **Throw** if `sha1s[slot]` is null/empty (message includes slot + instance id).
      - Return `undefined` when every pile has size 1 (no duplicates) — signals "no entry
        needed, scroller falls back to flat `group.slots`".
- [ ] Unit test: duplicates merged in first-seen order; all-unique → `undefined`;
      null → throws.

### T2. Pile storage on the result
- [ ] Add `pileIndex: Map<number, PileData>` to `GroupTree` (`GroupManager.ts`), init in
      constructor and `clear()`.
- [ ] Reset it at the start of each `group()` rebuild.

### T3. `applySha1Piles` pass (replaces groupBySha1 family)
- [ ] Add `private applySha1Piles()` on `GroupManager`: clear `pileIndex`; if
      `state.sha1Mode`, sweep every **final leaf** (`children.length === 0`), call
      `computeSha1Piles(group.slots, col.sha1s())`, store non-undefined results in
      `pileIndex`.
- [ ] Delete `groupBySha1`, `groupLeafsBySha1`, `removeSha1Groups`.
- [ ] `setSha1Mode(value)` → set flag, `applySha1Piles()`, `buildOrdinalRanges()`, emit.

### T4. Wire the pass into the pipeline (order: group → custom groups → sha1)
- [ ] `group()`: replace the `if (state.sha1Mode) this.groupLeafsBySha1()` block with a
      call to `applySha1Piles()`, placed **after** the custom-group replay loop.
- [ ] `addCustomGroups`: remove the `subGroupType == Cluster && sha1Mode` re-pile
      (`:828`); call `applySha1Piles()` at the end instead.
- [ ] `delCustomGroups`, `setAsRoot`: swap `groupBySha1(...)` calls for `applySha1Piles()`.
- [ ] `updateSelection`: remove the `removeSha1Groups()` at top and the
      `if (sha1Mode) groupLeafsBySha1()` before `buildOrdinalRanges`; call
      `applySha1Piles()` once before `buildOrdinalRanges()`.

### T5. `buildOrdinalRanges` reads piles
- [ ] Replace the `subGroupType === Sha1` branch: a leaf is piled iff
      `pileIndex.has(group.id)`. For a piled leaf, emit `pileData.order` into `orderedIds`
      (pile-ordered); per-pile start derives as `group.start + bounds[k]` (no stored child
      starts).
- [ ] Unpiled leaf path unchanged (emit `group.slots`).

### T6. Iterator reads piles (core of the change)
In `ImageIterator` (`GroupManager.ts`); for a piled leaf, `imageIdx` = pile index:
- [ ] `getSlots()` → `order.slice(bounds[i], bounds[i+1])`.
- [ ] Drop `sha1Group: Group`; expose the pile via the iterator's own `.slots`.
- [ ] `nextImages`/`prevImages` → bound with `bounds.length - 1` (pile count) instead of
      `group.children.length`.
- [ ] `getImageOrder()` → `group.start + bounds[imageIdx]`.
- [ ] `shouldSkipGroup`/`getSha1Group` → base "piled?" on `pileIndex.has(group.id)`, not
      `subGroupType === Sha1`.
- [ ] `GroupManager.findImageIterator` → for a piled leaf, find pile index by locating the
      target slot's position in `order` and mapping through `bounds` (no sha1 string
      compare).

### T7. Grid scroller renders piles
- [ ] `GridScroller.vue`: replace the `subGroupType === Sha1` / `group.children[i]` loop
      with a loop over `pileIndex.get(group.id)` piles; `PileRowLine.data` carries a pile
      handle `{ groupId, pileIndex, slots }` (not a child Group).
- [ ] `RowLine.vue` modal (`:173`): `getImageIterator(handle.groupId, handle.pileIndex)`.
- [ ] The "is this a leaf with real subgroups" check (`:158`) → `children.length > 0`
      (piled leaf is a genuine leaf now).

### T8. Tree scroller renders piles
- [ ] `TreeScroller.vue`: `subGroupType != Sha1` guards (`:170`,`:174`) → "leaf piled?"
      via `pileIndex.has(group.id)`; keep routing to `computeImagePileLines` (already
      iterator-driven, no change inside it).
- [ ] `Image.vue` count badge (`:109`) → `props.image.slots.length`.
- [ ] `GroupLine.vue` (`:48`,`:151`,`:169`) → drop `&& subGroupType != Sha1`; plain
      `children.length > 0`.

### T9. Remove structural `GroupType.Sha1`
- [ ] Delete `GroupType.Sha1` usages that were structural (subGroupType, child type).
      Keep the enum member only if still referenced; otherwise remove.
- [ ] Confirm `isSha1Group` (backend cluster flag, `utils.ts`) is untouched.

### T10. Verify Phase 1
- [ ] Tree + grid: identical piles + count badges as before.
- [ ] Toggle sha1Mode on/off repeatedly → no leaks, order restored from `group.slots`.
- [ ] Shift-select across piles; open image modal from a pile.
- [ ] Cluster + sha1Mode together; incremental update (`updateSelection`) while sha1 on.
- [ ] Confirm a forced null sha1 throws with a useful message.
- [ ] Memory/timing: no per-image Group/index/valueIndex growth in sha1Mode.

---

## Phase 2 — sha1 as final compose overlay (rides `refactor/collection_inspection_mission.md`)

Do after `GroupResult` is extracted and clusters move to a registry.

### T11. Move pile state to `GroupResult`
- [ ] Relocate `pileIndex` from `GroupTree` to `GroupResult`, beside
      `imageToGroups`/`orderedIds`.

### T12. Iterators take `GroupResult`
- [ ] `GroupIterator`/`ImageIterator` constructors take a `GroupResult`, not a
      `GroupManager`. Reads become `result.index` / `result.pileIndex` / `result.orderedIds`.
- [ ] Move the `iterators[]` registry + `isValid` invalidation onto `GroupResult`.

### T13. sha1 becomes the compose tail
- [ ] `applySha1Piles` becomes the **last** step of the compose pass (after clusters
      applied). Toggling sha1Mode re-runs only this step; revert = clear `pileIndex` +
      rebuild `orderedIds`, cluster comes back from the registry.
- [ ] Delete any remaining Phase-1 wiring that duplicated the pass across entry points.

### T14. Verify Phase 2
- [ ] Cluster → sha1 → revert leaves the cluster identical (recovered from registry).
- [ ] Iterators work with no `GroupManager` reference.

---

## Open items to confirm before/with T7–T8
- Cluster views wanting raw (un-piled) instances even under global sha1Mode — expected to
  be none; confirm.
- Scroller render-key + any persisted pile view-state — deferred; non-issues for the data
  model, settle when wiring scrollers.
