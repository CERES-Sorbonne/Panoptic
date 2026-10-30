// Markdown report of cache.sh: cold vs warm column loads, value rows vs cached column blob.
//   node cache-report.js <results/cache> <n>
const fs = require('fs')
const [dir, n] = process.argv.slice(2)
const rows = fs.readFileSync(`${dir}/cache-${n}.jsonl`, 'utf8').trim().split('\n').map(JSON.parse)
const file = rows.find(r => r.kind === 'cold-file')
const get = (op, variant, state) => rows.find(r => r.kind === 'cold' && r.op === op && r.variant === variant && r.state === state)
const ms = r => !r ? '—' : r.ms >= 1000 ? `${(r.ms / 1000).toFixed(2)} s` : r.ms >= 10 ? `${r.ms.toFixed(0)} ms` : r.ms >= 1 ? `${r.ms.toFixed(1)} ms` : `${r.ms.toFixed(2)} ms`
const mb = b => b >= 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${(b / 1e3).toFixed(0)} kB`
const x = (a, b) => a && b ? `${(a.ms / b.ms).toFixed(1)}×` : '—'

const ops = [...new Set(rows.filter(r => r.kind === 'cold' && r.op !== 'open').map(r => r.op))]
const coldRows = rows.filter(r => r.kind === 'cold' && r.state === 'cold')
const copyRes = Math.max(...coldRows.map(r => r.copy_resident ?? 0))
const reps = coldRows[0]?.reps

console.log(`# Cold column load, N = ${Number(n).toLocaleString('en-US')}

\`cache.db\` = the load bench's data.db plus a \`column_cache\` table: ${file ? mb(file.file_bytes) : '?'} file, blobs
${file ? mb(file.raw_bytes) : '?'} raw / ${file ? mb(file.zstd_bytes) : '?'} zstd for all columns. **Cold** = a fresh copy of
cache.db written with F_NOCACHE before each rep: at most ${(copyRes * 100).toFixed(1)}% of its pages were in the OS cache
after the copy (mincore). Open, schema and identity are read untimed, then one column is loaded.
**Warm** = the same load again on that connection. \`typed\` = rows → column (today's prototype
load), \`sqlite\` = the rows only, \`blob\` = cached column blob → column. Medians of ${reps}.
`)
console.log('| column | sqlite cold | typed cold | blob cold | zstd cold | typed warm | blob warm | zstd warm | blob | zstd blob | typed / blob cold |')
console.log('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
for (const op of ops) {
  const b = get(op, 'blob', 'cold'), z = get(op, 'blob-zstd', 'cold')
  console.log(`| ${op} | ${ms(get(op, 'sqlite', 'cold'))} | ${ms(get(op, 'typed', 'cold'))} | ${ms(b)} | ${ms(z)} | ${ms(get(op, 'typed', 'warm'))} | ${ms(get(op, 'blob', 'warm'))} | ${ms(get(op, 'blob-zstd', 'warm'))} | ${b ? mb(b.bytes) : '—'} | ${z ? mb(z.bytes) : '—'} | ${x(get(op, 'typed', 'cold'), b)} |`)
}
const sum = (variant, state) => {
  const r = ops.map(op => get(op, variant, state))
  return r.every(Boolean) ? { ms: r.reduce((a, b) => a + b.ms, 0) } : null
}
console.log(`| **sum** | **${ms(sum('sqlite', 'cold'))}** | **${ms(sum('typed', 'cold'))}** | **${ms(sum('blob', 'cold'))}** | **${ms(sum('blob-zstd', 'cold'))}** | **${ms(sum('typed', 'warm'))}** | **${ms(sum('blob', 'warm'))}** | **${ms(sum('blob-zstd', 'warm'))}** | | | **${x(sum('typed', 'cold'), sum('blob', 'cold'))}** |`)

const open = ['typed', 'blob', 'blob-zstd'].map(v => get('open', v, 'cold')).filter(Boolean)
if (open.length) {
  console.log(`
## Whole project open, cold

Fresh cold copy, then connection + schema + identity + every column, timed together.

| columns from | time | vs typed |
|---|---:|---:|`)
  for (const r of open) console.log(`| ${r.variant} | ${ms(r)} | ${x(open[0], r)} |`)
}
