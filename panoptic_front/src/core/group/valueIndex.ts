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
        let idx = this.index
        for (const value of valueKey) {
            if (!idx.has(value)) return
            idx = idx.get(value)
        }
        idx.delete(null)
    }
}
