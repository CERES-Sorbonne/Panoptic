/**
 * sha1 piles — display overlay for sha1Mode.
 *
 * Instead of materializing one Group per unique sha1, a leaf's instances stay a flat
 * array and piling is expressed as a permutation (`order`) plus per-pile boundaries
 * (`bounds`). A pile is a maximal run of slots sharing the same sha1, kept in
 * first-seen order (matching the previous groupBySha1 behaviour).
 *
 * Pure and store-agnostic: it takes the leaf's slots and the sha1-by-slot array.
 */

export interface PileData {
    // The leaf's slots, reordered so equal-sha1 slots are contiguous (first-seen order).
    order: number[]
    // First index of each pile within `order`; `bounds.length === numPiles + 1` with
    // `bounds[bounds.length - 1] === order.length`, so pile k is order[bounds[k]..bounds[k+1]].
    bounds: number[]
}

/**
 * Build the pile layout for a leaf.
 * Returns undefined only for an empty leaf (nothing to render). A leaf with no duplicate
 * sha1s still gets a layout of singleton piles (order === slots, bounds === [0..n]) so
 * that, in sha1Mode, EVERY leaf renders through the same pile path — same row height and
 * same sha1-property set — instead of some leaves falling back to the flat image path.
 *
 * A slot with no sha1 gets its own singleton pile: without a hash it cannot be known to be
 * a duplicate of anything. It is never dropped, so `order` stays a permutation of `slots`
 * and the display order stays aligned with the group's membership. That case is still an
 * invariant breach (sha1 is written eagerly at instance creation), so it is reported once
 * per call with console.warn — loud, but not a crash: this runs inside synchronous
 * structural edits that would otherwise be left half-applied.
 */
export function computeSha1Piles(slots: number[], sha1s: (string | null)[], instanceIds?: Int32Array): PileData | undefined {
    if (slots.length === 0) return undefined

    // Piles in first-seen order. A sha1 maps to its bucket; a sha1-less slot opens a bucket
    // of its own that nothing else can ever join.
    const bucketOf = new Map<string, number[]>()
    const piles: number[][] = []
    let missing = 0
    let firstMissing = -1

    for (const s of slots) {
        const sha1 = sha1s[s]
        if (!sha1) {
            missing++
            if (firstMissing < 0) firstMissing = s
            piles.push([s])
            continue
        }
        let bucket = bucketOf.get(sha1)
        if (!bucket) {
            bucket = []
            bucketOf.set(sha1, bucket)
            piles.push(bucket)
        }
        bucket.push(s)
    }

    if (missing > 0) {
        const who = instanceIds ? ` (instance ${instanceIds[firstMissing]})` : ''
        console.warn(`sha1 pile: ${missing}/${slots.length} slot(s) have no sha1, `
            + `e.g. slot ${firstMissing}${who}; each is piled alone`)
    }

    const order = new Array<number>(slots.length)
    const bounds = new Array<number>(piles.length + 1)
    let pos = 0
    for (let k = 0; k < piles.length; k++) {
        bounds[k] = pos
        for (const s of piles[k]) order[pos++] = s
    }
    bounds[piles.length] = pos

    return { order, bounds }
}

/** Number of piles described by a PileData. */
export function pileCount(pile: PileData): number {
    return pile.bounds.length - 1
}

/** Slots of pile k (a view into order via bounds). */
export function pileSlots(pile: PileData, k: number): number[] {
    return pile.order.slice(pile.bounds[k], pile.bounds[k + 1])
}

/** Pile index that contains `slot`, or -1 if the slot is not in this pile layout. */
export function pileIndexOfSlot(pile: PileData, slot: number): number {
    const offset = pile.order.indexOf(slot)
    if (offset < 0) return -1
    const { bounds } = pile
    for (let k = 0; k < bounds.length - 1; k++) {
        if (offset < bounds[k + 1]) return k
    }
    return bounds.length - 2
}
