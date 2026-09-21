/**
 * GroupValueIndex — persistent value-key → stable-id map.
 * Group IDs stay stable across rebuilds (so view state / collapse survives) because a
 * given value-key always resolves to the same minted id. Nested Map keyed by each value
 * in the key, with the id stored under the `null` leaf slot.
 */
export class GroupValueIndex {
    index: Map<any, any>
    private idCounter: number

    constructor() {
        this.index = new Map()
        this.idCounter = 1
    }

    get(valueKey: any[]) {
        let idx = this.index
        for (const value of valueKey) {
            if (!idx.has(value)) idx.set(value, new Map())
            idx = idx.get(value)
        }
        if (!idx.has(null)) {
            idx.set(null, this.idCounter++)
        }
        return idx.get(null)
    }

    delete(valueKey: any[]) {
        // Remember the node each step came from, so the empty ones can be dropped on the way
        // back up: removing only the `null` leaf left the whole chain of Maps minted for this
        // key alive, one node per distinct value ever seen.
        const path: { map: Map<any, any>, value: any }[] = []
        let idx = this.index
        for (const value of valueKey) {
            if (!idx.has(value)) return
            path.push({ map: idx, value })
            idx = idx.get(value)
        }
        idx.delete(null)
        // Stop at the first node that still holds something — a sibling key sharing this
        // prefix, or a deeper key below it — so pruning one key never touches another.
        for (let i = path.length - 1; i >= 0; i--) {
            const { map, value } = path[i]
            if (map.get(value).size > 0) break
            map.delete(value)
        }
    }
}
