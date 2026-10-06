import { test } from 'node:test'
import assert from 'node:assert/strict'
import { edgeArrow, konamiMatcher, SnakeGame, type Cell } from '@/mixins/mapview/GridSnake'
import { rng } from '../harness/data'

const board = { c0: 10, r0: 20, cols: 12, rows: 8 }

function allCells(b = board): Cell[] {
    const res: Cell[] = []
    for (let c = b.c0; c < b.c0 + b.cols; c++) for (let r = b.r0; r < b.r0 + b.rows; r++) res.push({ c, r })
    return res
}

test('snake: starts centred, heading right, food on an image off the snake', () => {
    const g = new SnakeGame(board, allCells(), rng(1))
    assert.deepEqual(g.body, [{ c: 16, r: 24 }, { c: 15, r: 24 }, { c: 14, r: 24 }])
    assert.ok(g.food)
    assert.ok(!g.body.some(p => p.c === g.food!.c && p.r === g.food!.r))
    assert.equal(g.step(), 'moved')
    assert.deepEqual(g.body[0], { c: 17, r: 24 })
    assert.equal(g.body.length, 3)
})

test('snake: food only ever lands on image cells', () => {
    const images = [{ c: 11, r: 21 }, { c: 20, r: 26 }]
    for (let seed = 0; seed < 20; seed++) {
        const g = new SnakeGame(board, images, rng(seed))
        assert.ok(images.some(p => p.c === g.food!.c && p.r === g.food!.r))
    }
})

test('snake: eating scores, grows by two and moves the food', () => {
    const g = new SnakeGame(board, [{ c: 17, r: 24 }, { c: 11, r: 21 }], rng(1))
    g.food = { c: 17, r: 24 }
    assert.equal(g.step(), 'ate')
    assert.equal(g.score, 1)
    assert.deepEqual(g.food, { c: 11, r: 21 })
    g.step(); g.step(); g.step()
    assert.equal(g.body.length, 5)
})

test('snake: eating the last image wins', () => {
    const g = new SnakeGame(board, [{ c: 17, r: 24 }], rng(1))
    assert.equal(g.step(), 'won')
    assert.equal(g.state, 'won')
    assert.equal(g.step(), 'won', 'no more moves once finished')
})

test('snake: the board edge is a wall', () => {
    const g = new SnakeGame(board, allCells(), rng(1))
    g.food = null
    let result = ''
    for (let i = 0; i < 10 && result !== 'over'; i++) result = g.step()
    assert.equal(result, 'over')
    assert.equal(g.body[0].c, board.c0 + board.cols - 1, 'died against the right wall')
})

test('snake: no U-turn, and two quick turns both apply', () => {
    const g = new SnakeGame(board, allCells(), rng(1))
    g.turn('left')
    g.step()
    assert.deepEqual(g.body[0], { c: 17, r: 24 }, 'reversing is ignored')
    g.turn('up')
    g.turn('left')
    g.step()
    g.step()
    assert.deepEqual(g.body[0], { c: 16, r: 25 })
})

test('snake: running into itself ends the game, chasing its tail does not', () => {
    const g = new SnakeGame(board, allCells(), rng(1))
    g.body = [{ c: 15, r: 24 }, { c: 14, r: 24 }, { c: 14, r: 25 }, { c: 15, r: 25 }, { c: 16, r: 25 }]
    g.turn('up')
    assert.equal(g.step(), 'over')

    const h = new SnakeGame(board, allCells(), rng(1))
    h.body = [{ c: 15, r: 24 }, { c: 14, r: 24 }, { c: 14, r: 25 }, { c: 15, r: 25 }]
    h.food = null
    h.turn('up')
    assert.equal(h.step(), 'moved', 'the tail cell frees up as the head enters it')
})

test('snake: starts where asked, kept inside the board with room for its body', () => {
    const grid = { c0: 0, r0: 0, cols: 400, rows: 300 }
    assert.deepEqual(new SnakeGame(grid, [], rng(1), { c: 120, r: 80 }).body[0], { c: 120, r: 80 })
    assert.deepEqual(new SnakeGame(grid, [], rng(1), { c: 0, r: 500 }).body, [{ c: 2, r: 299 }, { c: 1, r: 299 }, { c: 0, r: 299 }])
})

test('snake: food can spawn anywhere on the grid', () => {
    const grid = { c0: 0, r0: 0, cols: 400, rows: 300 }
    const images = [{ c: 390, r: 290 }, { c: 210, r: 155 }, { c: 5, r: 5 }]
    const seen = new Set<string>()
    for (let seed = 0; seed < 50; seed++) {
        const f = new SnakeGame(grid, images, rng(seed), { c: 200, r: 150 }).food!
        seen.add(`${f.c},${f.r}`)
    }
    assert.equal(seen.size, 3, 'far images are drawn too')
})

test('edgeArrow: hidden on screen, pinned to the edge towards the target otherwise', () => {
    const view = { minX: -10, minY: -5, maxX: 10, maxY: 5 }
    assert.equal(edgeArrow(view, { x: 3, y: -4 }), null)

    const right = edgeArrow(view, { x: 40, y: 0 })!
    assert.deepEqual([right.x, right.y, right.angle], [10, 0, 0])

    const up = edgeArrow(view, { x: 0, y: 100 })!
    assert.deepEqual([up.x, up.y], [0, 5])
    assert.ok(Math.abs(up.angle - Math.PI / 2) < 1e-9)

    const corner = edgeArrow(view, { x: -40, y: -40 })!
    assert.deepEqual([corner.x, corner.y], [-5, -5], 'hits the nearer edge (bottom) first')
    assert.ok(Math.abs(corner.angle + 3 * Math.PI / 4) < 1e-9)
})

test('konami: fires on the full sequence only, tolerant to a stray prefix', () => {
    const code = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a']
    const m = konamiMatcher()
    assert.deepEqual(code.map(m), [...new Array(9).fill(false), true])
    const n = konamiMatcher()
    assert.equal(['ArrowUp', ...code.slice(0, -1), 'A'].map(n).pop(), true, 'extra leading up, capital A')
    const o = konamiMatcher()
    assert.equal([...code.slice(0, 5), 'x', ...code.slice(5)].map(o).includes(true), false)
})
