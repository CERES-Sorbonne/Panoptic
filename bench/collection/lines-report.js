// Joins results/lines/<impl>-<n>.jsonl into markdown tables (scroller line layout, front JS vs Rust)
// and checks that every implementation produced the same lines.
//   node lines-report.js results/lines 1000000
const fs = require('fs'), path = require('path')
const [dir, n] = process.argv.slice(2)
const rows = fs.readdirSync(dir).filter(f => f.endsWith(`-${n}.jsonl`))
    .flatMap(f => fs.readFileSync(path.join(dir, f), 'utf8').trim().split('\n').filter(l => l.startsWith('{')).map(JSON.parse))
    .filter(r => r.op)
const order = ['v8', 'jsc', 'rust-1t', ...[...new Set(rows.map(r => r.impl))].filter(i => /^rust-\d+t$/.test(i) && i !== 'rust-1t')]
const impls = order.filter(i => rows.some(r => r.impl === i))
const par = impls.filter(i => i.startsWith('rust')).pop()
const get = (impl, view, tree, cfg, op) => rows.find(r => r.impl === impl && r.view === view && r.tree === tree && r.cfg === cfg && r.op === op)
const ms = (v) => v == null ? '—' : v >= 1000 ? (v / 1000).toFixed(2) + ' s' : v >= 10 ? v.toFixed(0) + ' ms'
    : v >= 1 ? v.toFixed(1) + ' ms' : v >= 0.001 ? (v * 1000).toFixed(v >= 0.1 ? 0 : 1) + ' µs' : (v * 1e6).toFixed(0) + ' ns'
const x = (a, b) => a == null || b == null || !b ? '—' : (a / b >= 10 ? (a / b).toFixed(0) : (a / b).toFixed(1)) + '×'
const int = (v) => v == null ? '—' : Number(v).toLocaleString('en')
const CHECK = ['lines', 'height', 'hash', 'layout_height', 'nodes']
const same = (rs) => {
    const sigs = new Set(rs.filter(Boolean).map(r => CHECK.map(k => r[k]).join('/')))
    return sigs.size <= 1 ? 'yes' : 'NO'
}
const table = (head, body) => {
    console.log('| ' + head.join(' | ') + ' |')
    console.log('|' + head.map((_, i) => i ? '---:' : '---').join('|') + '|')
    for (const r of body) console.log('| ' + r.join(' | ') + ' |')
    console.log()
}
const trees = [...new Set(rows.map(r => r.tree))]
const VIEW = { grid: 'Grid view (TreeScroller: images per line from the width)', table: 'Table view (GridScroller: one row per image)' }
const BASE = { grid: 'w1440 i200', table: 'row104' }
const OPS = ['build', 'toggle one', 'close all', 'open all', 'locate', 'offsetOf', 'window', 'measure screen']

console.log(`\n# Scroller lines, N = ${int(n)}\n`)
console.log('Front = the real scrollLayout.ts / treeLines.ts / gridLines.ts under V8 and JSC. Rust = the same layout')
console.log('over the engine\'s own tree (rust/src/lines.rs). Medians; locate/offsetOf per call; window = one')
console.log('VirtualScroller.update walk (1000 px viewport + 300 px overscan) making its line objects.\n')

for (const view of ['grid', 'table']) {
    if (!rows.some(r => r.view === view)) continue
    console.log(`## ${VIEW[view]}\n`)
    console.log(`### Layout ops (${view === 'grid' ? '1440 px wide, 200 px images, 2 properties' : 'row estimate 104 px'})\n`)
    const body = []
    for (const tree of trees) {
        const b = get(impls[0], view, tree, BASE[view], 'build') ?? get(par, view, tree, BASE[view], 'build')
        for (const op of OPS) {
            const rs = impls.map(i => get(i, view, tree, BASE[view], op))
            if (!rs.some(Boolean)) continue
            const info = op === 'build' ? `${int(b?.groups)} groups` : op === 'window' ? `${rs.find(Boolean).lines} lines` : op === 'measure screen' ? `${rs.find(Boolean).rows} rows` : ''
            const checks = rs.filter(r => r && r.hash !== undefined)
            const ok = checks.length ? (new Set(checks.map(r => r.hash)).size === 1 ? 'yes' : 'NO') : ''
            body.push([tree, op, info, ...rs.map(r => ms(r?.ms)), x(get('jsc', view, tree, BASE[view], op)?.ms, get(par, view, tree, BASE[view], op)?.ms), ok])
        }
    }
    table(['tree', 'op', '', ...impls, `jsc vs ${par}`, 'same'], body)

    console.log(`### ${view === 'grid' ? 'Resize' : 'Row size change'} (layout.refresh) and every line object (eager)\n`)
    const body2 = []
    for (const tree of trees) {
        const cfgs = [...new Set(rows.filter(r => r.view === view && r.tree === tree && r.op === 'all lines').map(r => r.cfg))]
        for (const cfg of cfgs) {
            const relay = impls.map(i => get(i, view, tree, cfg, view === 'grid' ? 'resize' : 'row size'))
            const all = impls.map(i => get(i, view, tree, cfg, 'all lines'))
            const a = all.find(Boolean)
            body2.push([tree, cfg, int(a.lines), int(a.height) + ' px', ...relay.map(r => ms(r?.ms)), ...all.map(r => ms(r?.ms)), same(all)])
        }
    }
    table(['tree', 'config', 'lines', 'height', ...impls.map(i => 'refresh ' + i), ...impls.map(i => 'all lines ' + i), 'same'], body2)
}
