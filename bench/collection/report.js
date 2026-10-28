// Joins results/<impl>-<n>.jsonl into a markdown table and checks every impl agrees on each result.
//   node report.js results 1000000
const fs = require('fs'), path = require('path')
const [dir, n] = process.argv.slice(2)
const rows = fs.readdirSync(dir).filter(f => f.endsWith(`-${n}.jsonl`))
    .flatMap(f => fs.readFileSync(path.join(dir, f), 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse))
    .filter(r => !r.meta)
const impls = ['v8', 'jsc', 'v8-raw', 'rust-1t', ...[...new Set(rows.map(r => r.impl))].filter(i => /^rust-\d+t$/.test(i) && i !== 'rust-1t')]
    .filter(i => rows.some(r => r.impl === i))
const par = impls.filter(i => i.startsWith('rust-')).pop()
const ops = [...new Map(rows.map(r => [r.kind + ': ' + r.op, r])).keys()]
const fmt = (ms) => ms == null ? '—' : ms >= 1000 ? (ms / 1000).toFixed(2) + ' s' : ms >= 10 ? ms.toFixed(0) + ' ms' : ms.toFixed(1) + ' ms'
const x = (a, b) => a == null || b == null ? '—' : (a / b >= 10 ? (a / b).toFixed(0) : (a / b).toFixed(1)) + '×'
const get = (op, impl) => rows.find(r => r.kind + ': ' + r.op === op && r.impl === impl)

const head = ['op', ...impls, `${par} vs v8`, `${par} vs jsc`, 'same result']
console.log(`\nN = ${Number(n).toLocaleString('en')}  (median ms)\n`)
console.log('| ' + head.join(' | ') + ' |')
console.log('|' + head.map((_, i) => i ? '---:' : '---').join('|') + '|')
const tot = Object.fromEntries(impls.map(i => [i, 0]))
for (const op of ops) {
    const rs = impls.map(i => get(op, i))
    const sigs = new Set(rs.filter(Boolean).map(r => `${r.count}/${r.entries}/${r.hash}`))
    rs.forEach((r, k) => { if (r) tot[impls[k]] += r.ms })
    const v8 = get(op, 'v8')?.ms, jsc = get(op, 'jsc')?.ms, rp = get(op, par)?.ms
    console.log('| ' + [op, ...rs.map(r => fmt(r?.ms)), x(v8, rp), x(jsc, rp), sigs.size === 1 ? 'yes' : 'NO'].join(' | ') + ' |')
}
console.log('| **total** | ' + impls.map(i => '**' + fmt(tot[i]) + '**').join(' | ') + ` | **${x(tot.v8 || null, tot[par])}** | **${x(tot.jsc || null, tot[par])}** | |`)
