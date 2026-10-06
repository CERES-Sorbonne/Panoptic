export type SnakeDir = 'up' | 'down' | 'left' | 'right'
export type SnakeState = 'running' | 'over' | 'won'

export interface Cell { c: number, r: number }

// Area the game is played on; its edges are walls.
export interface SnakeBoard { c0: number, r0: number, cols: number, rows: number }

const DELTA: Record<SnakeDir, Cell> = {
    up: { c: 0, r: 1 },
    down: { c: 0, r: -1 },
    left: { c: -1, r: 0 },
    right: { c: 1, r: 0 },
}
const OPPOSITE: Record<SnakeDir, SnakeDir> = { up: 'down', down: 'up', left: 'right', right: 'left' }
const START_LENGTH = 3
const GROWTH = 2

export class SnakeGame {
    // Head first.
    public body: Cell[] = []
    public food: Cell | null = null
    public score = 0
    public state: SnakeState = 'running'
    private dir: SnakeDir = 'right'
    private turns: SnakeDir[] = []
    private pendingGrowth = 0

    // `images`: cells of the board holding an image — the only cells food can appear on.
    // `start`: where the head starts (board centre by default), heading right.
    constructor(public board: SnakeBoard, private images: Cell[], private rand: () => number = Math.random, start?: Cell) {
        const length = Math.min(START_LENGTH, board.cols)
        const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))
        const head = clamp(start?.c ?? board.c0 + Math.floor(board.cols / 2), board.c0 + length - 1, board.c0 + board.cols - 1)
        const r = clamp(start?.r ?? board.r0 + Math.floor(board.rows / 2), board.r0, board.r0 + board.rows - 1)
        for (let i = 0; i < length; i++) this.body.push({ c: head - i, r })
        this.placeFood()
    }

    // Queued so two quick key presses inside one tick both apply.
    public turn(dir: SnakeDir) {
        const last = this.turns.length ? this.turns[this.turns.length - 1] : this.dir
        if (dir === last || dir === OPPOSITE[last] || this.turns.length >= 2) return
        this.turns.push(dir)
    }

    public step(): 'moved' | 'ate' | 'over' | 'won' {
        if (this.state !== 'running') return this.state
        if (this.turns.length) this.dir = this.turns.shift()!
        const d = DELTA[this.dir]
        const head = { c: this.body[0].c + d.c, r: this.body[0].r + d.r }
        const b = this.board
        if (head.c < b.c0 || head.c >= b.c0 + b.cols || head.r < b.r0 || head.r >= b.r0 + b.rows) {
            this.state = 'over'
            return 'over'
        }
        // The tail moves out of the way this step unless the snake is growing.
        const solid = this.pendingGrowth > 0 ? this.body : this.body.slice(0, -1)
        if (solid.some(p => p.c === head.c && p.r === head.r)) {
            this.state = 'over'
            return 'over'
        }

        this.body.unshift(head)
        if (this.pendingGrowth > 0) this.pendingGrowth--
        else this.body.pop()

        if (this.food && head.c === this.food.c && head.r === this.food.r) {
            this.score++
            this.pendingGrowth += GROWTH
            this.placeFood()
            if (!this.food) {
                this.state = 'won'
                return 'won'
            }
            return 'ate'
        }
        return 'moved'
    }

    private placeFood() {
        const taken = new Set(this.body.map(p => `${p.c},${p.r}`))
        const free = this.images.filter(p => !taken.has(`${p.c},${p.r}`))
        this.food = free.length ? free[Math.floor(this.rand() * free.length)] : null
    }
}

export interface Rect { minX: number, minY: number, maxX: number, maxY: number }

// Arrow pointing from the centre of `view` towards `target`, pinned to the view's edge; null while
// the target is inside the view.
export function edgeArrow(view: Rect, target: { x: number, y: number }): { x: number, y: number, angle: number } | null {
    if (target.x >= view.minX && target.x <= view.maxX && target.y >= view.minY && target.y <= view.maxY) return null
    const cx = (view.minX + view.maxX) / 2, cy = (view.minY + view.maxY) / 2
    const dx = target.x - cx, dy = target.y - cy
    const t = Math.min(
        dx ? (view.maxX - view.minX) / 2 / Math.abs(dx) : Infinity,
        dy ? (view.maxY - view.minY) / 2 / Math.abs(dy) : Infinity,
    )
    return { x: cx + dx * t, y: cy + dy * t, angle: Math.atan2(dy, dx) }
}

const KONAMI = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a']

// Feed it every key; returns true on the key completing the sequence.
export function konamiMatcher() {
    const last: string[] = []
    return (key: string) => {
        last.push(key.length === 1 ? key.toLowerCase() : key)
        if (last.length > KONAMI.length) last.shift()
        if (last.length === KONAMI.length && last.every((k, i) => k === KONAMI[i])) {
            last.length = 0
            return true
        }
        return false
    }
}
