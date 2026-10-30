// Joins results/load/<impl>-<n>.jsonl into a markdown table: loading one full property column
// from data.db into the Rust engine's store vs today's Python route + the webview's ingest.
//   node load-report.js results/load 1000000
const fs = require('fs'), path = require('path')
const [dir, n] = process.argv.slice(2)
const rows = fs.readdirSync(dir).filter(f => f.endsWith(`-${n}.jsonl`))
    .flatMap(f => fs.readFileSync(path.join(dir, f), 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse))
const get = (impl, op, variant) => rows.find(r => r.impl === impl && r.op === op
    && (variant == null ? r.kind === 'wire' : r.kind === 'load' && r.variant === variant))

const ms = (v) => v == null ? '—' : v >= 1000 ? (v / 1000).toFixed(2) + ' s' : v >= 10 ? v.toFixed(0) + ' ms'
    : v >= 1 ? v.toFixed(1) + ' ms' : (v * 1000).toFixed(v >= 0.1 ? 0 : 1) + ' µs'
const size = (b) => b == null ? '—' : b >= 1 << 20 ? (b / (1 << 20)).toFixed(1) + ' MB' : b >= 1024 ? (b / 1024).toFixed(1) + ' KB' : b + ' B'
const add = (...v) => v.some(x => x == null) ? null : v.reduce((a, b) => a + b, 0)
const ratio = (a, b) => a == null || b == null ? '—' : (a / b).toFixed(a / b >= 10 ? 0 : 1) + '×'
const table = (head, body) => {
    console.log('| ' + head.join(' | ') + ' |')
    console.log('|' + head.map((_, i) => i ? '---:' : '---').join('|') + '|')
    for (const r of body) console.log('| ' + r.join(' | ') + ' |')
    console.log()
}

const N = Number(n).toLocaleString('en')
console.log(`\n# Full column load, N = ${N}\n`)
console.log('Same data.db (Python schema, warm OS cache) for both sides. Rust = the prototype store')
console.log('(`load/src/store.rs`) on one long-lived read connection: `typed` builds the column directly,')
console.log('`generic` goes through `serde_json::Value` + `CellValue::from_json` + `SetValues`. Python =')
console.log('the real route, body iterated in-process (no HTTP), new reader per request as in the app.')
console.log('JSC = the webview ingest (`js/wire.js`) of the bytes that route produced. Medians.\n')

const cols = rows.filter(r => r.impl === 'rust' && r.kind === 'load' && r.variant === 'typed' && r.op !== 'schema')
const tot = { rs: 0, rt: 0, rg: 0, ps: 0, pr: 0, jsc: 0, bytes: 0 }
const body = cols.map(c => {
    const rs = get('rust', c.op, 'sqlite')?.ms, rg = get('rust', c.op, 'generic')?.ms
    const ps = get('python', c.op, 'sqlite')?.ms, pr = get('python', c.op, 'route')
    const jsc = get('jsc', c.op)?.ms
    const today = c.op === 'base' ? pr?.ms : add(pr?.ms, jsc)
    if (c.op !== 'base') {
        tot.rs += rs; tot.rt += c.ms; tot.rg += rg ?? NaN; tot.ps += ps ?? NaN; tot.pr += pr?.ms ?? NaN
        tot.jsc += jsc ?? NaN; tot.bytes += pr?.bytes ?? NaN
    }
    return [c.op, (c.rows ?? c.count).toLocaleString('en'), ms(rs), ms(c.ms), ms(rg), ms(ps), ms(pr?.ms), size(pr?.bytes),
        c.op === 'base' ? 'n/a' : ms(jsc), ms(today), ratio(pr?.ms, c.ms), c.op === 'base' ? '—' : ratio(today, c.ms)]
})
const nan = (v) => Number.isNaN(v) ? null : v
body.push(['**all 7 columns**', '', `**${ms(tot.rs)}**`, `**${ms(tot.rt)}**`, `**${ms(nan(tot.rg))}**`, `**${ms(nan(tot.ps))}**`,
    `**${ms(nan(tot.pr))}**`, `**${size(nan(tot.bytes))}**`, `**${ms(nan(tot.jsc))}**`, `**${ms(add(nan(tot.pr), nan(tot.jsc)))}**`,
    `**${ratio(nan(tot.pr), tot.rt)}**`, `**${ratio(add(nan(tot.pr), nan(tot.jsc)), tot.rt)}**`])
table(['column', 'rows', 'rust sqlite', 'rust typed', 'rust generic', 'py sqlite', 'py route', 'route bytes',
    'jsc ingest', 'today (route + jsc)', 'route / typed', 'today / typed'], body)

const open = get('python', 'reader', 'open')
if (open) console.log(`Every Python timing includes one DataReader open + close: ${ms(open.ms)}.\n`)
const checks = rows.filter(r => r.impl === 'python' && r.variant === 'route' && r.ids != null && r.ids !== r.distinct_ids)
for (const c of checks) console.log(`⚠ ${c.op}: the route sent ${c.ids.toLocaleString('en')} ids for ${c.distinct_ids.toLocaleString('en')} instances (an instance split across two batches).`)
if (checks.length) console.log()
