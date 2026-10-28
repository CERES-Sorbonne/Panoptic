// Joins results/wire/<impl>-<n>.jsonl into markdown tables: today's full-column stream against
// windowed payloads, encode on the server side and decode in the webview engines.
//   node wire-report.js results/wire 1000000
const fs = require('fs'), path = require('path')
const [dir, n] = process.argv.slice(2)
const rows = fs.readdirSync(dir).filter(f => f.endsWith(`-${n}.jsonl`))
    .flatMap(f => fs.readFileSync(path.join(dir, f), 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse))
    .filter(r => r.kind === 'wire')
const get = (impl, group, op, fmt, lib) => rows.find(r => r.impl === impl && r.group === group && r.op === op
    && (fmt == null || r.fmt === fmt) && (lib == null || r.lib === lib))
const has = (impl) => rows.some(r => r.impl === impl)

const ms = (v) => v == null ? '—' : v >= 1000 ? (v / 1000).toFixed(2) + ' s' : v >= 10 ? v.toFixed(0) + ' ms'
    : v >= 1 ? v.toFixed(1) + ' ms' : (v * 1000).toFixed(v >= 0.1 ? 0 : 1) + ' µs'
const size = (b) => b >= 1 << 20 ? (b / (1 << 20)).toFixed(1) + ' MB' : b >= 1024 ? (b / 1024).toFixed(1) + ' KB' : b + ' B'
const add = (...v) => v.some(x => x == null) ? null : v.reduce((a, b) => a + b, 0)
const table = (head, body) => {
    console.log('| ' + head.join(' | ') + ' |')
    console.log('|' + head.map((_, i) => i ? '---:' : '---').join('|') + '|')
    for (const r of body) console.log('| ' + r.join(' | ') + ' |')
    console.log()
}

const N = Number(n).toLocaleString('en')
console.log(`\n# Wire cost, N = ${N}\n`)
console.log('Encode: Python = msgspec.json.encode of the prebuilt line structs (what get_property_column')
console.log('runs per batch, SQLite read and list building excluded); Rust = serde_json / rmp-serde,')
console.log('building the window from the columns included. Decode: V8 = node, JSC = macOS jsc shell')
console.log('(the Tauri webview engine). Transport is not measured. Medians.\n')

// ── today's stream ──
const streams = rows.filter(r => r.impl === 'rust' && r.group === 'stream')
console.log(`## Today: \`/instances/column/{id}\` NDJSON, whole column\n`)
const sTot = { bytes: 0, py: 0, rust: 0, v8: 0, jsc: 0 }
const sBody = streams.map(s => {
    const py = get('python', 'stream', s.op)?.ms, v8 = get('v8', 'stream', s.op)?.ms, jsc = get('jsc', 'stream', s.op)?.ms
    sTot.bytes += s.bytes; sTot.rust += s.ms; sTot.py += py ?? NaN; sTot.v8 += v8 ?? NaN; sTot.jsc += jsc ?? NaN
    return [s.op, s.col_kind, size(s.bytes), ms(py), ms(s.ms), ms(v8), ms(jsc), ms(add(py, jsc))]
})
const nan = (v) => Number.isNaN(v) ? null : v
sBody.push(['**all 7**', '', `**${size(sTot.bytes)}**`, `**${ms(nan(sTot.py))}**`, `**${ms(sTot.rust)}**`,
    `**${ms(nan(sTot.v8))}**`, `**${ms(nan(sTot.jsc))}**`, `**${ms(add(nan(sTot.py), nan(sTot.jsc)))}**`])
table(['column', 'kind', 'bytes', 'encode py', 'encode rust', 'ingest v8', 'ingest jsc', 'py + jsc'], sBody)
const pySame = rows.filter(r => r.impl === 'python' && r.group === 'stream')
if (pySame.length) console.log(`msgspec re-encode is byte-identical to the Rust replica: ${pySame.every(r => r.same_bytes) ? 'yes' : 'NO'}\n`)

// ── windows / pages / headers ──
const libs = [['json', 'JSON.parse'], ['msgpack', 'msgpackr'], ['msgpack', '@msgpack/msgpack']]
function payloadTable(group, title) {
    const encs = rows.filter(r => r.impl === 'rust' && r.group === group)
    if (!encs.length) return
    console.log(`## ${title}\n`)
    const body = []
    for (const e of encs) {
        for (const [fmt, lib] of libs) {
            if (e.fmt !== fmt) continue
            const v8 = get('v8', group, e.op, fmt, lib), jsc = get('jsc', group, e.op, fmt, lib)
            const same = [v8, jsc].filter(r => r && r.same !== undefined)
            const count = e.rows != null ? e.rows : e.groups
            body.push([e.op, count, lib, size(e.bytes), ms(e.ms), ms(v8?.ms), ms(jsc?.ms), ms(add(e.ms, jsc?.ms)),
                same.length ? (same.every(r => r.same) ? 'yes' : 'NO') : ''])
        }
    }
    table(['payload', group === 'headers' ? 'groups' : 'images', 'decoder', 'bytes', 'encode rust', 'decode v8',
        'decode jsc', 'rust + jsc', 'same as json'], body)
}
payloadTable('window', 'Window: rows `[N/2, N/2 + w)` of the collection sorted by label, score desc, all 7 properties')
const lays = rows.filter(r => r.impl === 'rust' && r.group === 'layout')
payloadTable('page', 'Group page: 50 lines (headers + rows of 10 images) from the middle of the tree, plus their values')
if (lays.length) {
    console.log('Line layout of the tree (once per regroup, then every page is a binary search):\n')
    table(['tree', 'groups', 'lines', 'layout rust'], lays.map(l => [l.op, l.groups.toLocaleString('en'), l.total_lines.toLocaleString('en'), ms(l.ms)]))
}
payloadTable('headers', 'Every group header of the tree (to size the whole scroll)')

// ── summary ──
const w = get('rust', 'window', '500 cols', 'msgpack'), wj = get('rust', 'window', '500 rows', 'json')
if (w && streams.length) {
    const wJsc = get('jsc', 'window', '500 cols', 'msgpack', 'msgpackr')?.ms
    const wjJsc = get('jsc', 'window', '500 rows', 'json', 'JSON.parse')?.ms
    const today = add(nan(sTot.py), nan(sTot.jsc))
    console.log('## Per scroll vs today\n')
    table(['', 'bytes', 'server + jsc', 'vs all 7 columns today'], [
        ['all 7 columns, today', size(sTot.bytes), ms(today), '1×'],
        ['500-row window, json rows', size(wj.bytes), ms(add(wj.ms, wjJsc)), `1/${Math.round(sTot.bytes / wj.bytes).toLocaleString('en')} bytes, 1/${today && wjJsc ? Math.round(today / (wj.ms + wjJsc)).toLocaleString('en') : '—'} time`],
        ['500-row window, msgpack cols', size(w.bytes), ms(add(w.ms, wJsc)), `1/${Math.round(sTot.bytes / w.bytes).toLocaleString('en')} bytes, 1/${today && wJsc ? Math.round(today / (w.ms + wJsc)).toLocaleString('en') : '—'} time`],
    ])
}
