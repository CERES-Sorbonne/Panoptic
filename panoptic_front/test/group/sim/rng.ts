/**
 * Seeded PRNG for the simulation. mulberry32: 32 bits of state, so a run is fully described by
 * its seed and nothing about the host (Math.random, time, iteration order) reaches it.
 */
export class Rng {
    private s: number

    constructor(seed: number) { this.s = seed | 0 }

    next(): number {
        this.s = (this.s + 0x6D2B79F5) | 0
        let t = Math.imul(this.s ^ (this.s >>> 15), 1 | this.s)
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296
    }

    /** Integer in [0, n). */
    int(n: number): number { return n <= 0 ? 0 : Math.floor(this.next() * n) % n }

    /** Integer in [lo, hi]. */
    between(lo: number, hi: number): number { return lo + this.int(hi - lo + 1) }

    chance(p: number): boolean { return this.next() < p }

    pick<T>(arr: T[]): T { return arr[this.int(arr.length)] }

    /** A new array holding a random subset of `arr`, each element kept with probability `p`. */
    subset<T>(arr: T[], p: number): T[] { return arr.filter(() => this.chance(p)) }
}
