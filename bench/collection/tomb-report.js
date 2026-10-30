// Markdown report of results/tomb/tomb-<n>.jsonl.  node tomb-report.js <dir> <n>
const fs = require('fs')
const [dir, n] = process.argv.slice(2)
const rows = fs.readFileSync(`${dir}/tomb-${n}.jsonl`, 'utf8').trim().split('\n').map(JSON.parse)
const VARIANTS = ['inline', 'lean', 'table', 'full']
const deads = [...new Set(rows.map(r => r.dead))].sort((a, b) => a - b)
const get = (v, d, op, f = () => true) => rows.find(r => r.variant === v && r.dead === d && r.op === op && f(r))
const f1 = x => x == null ? '' : x < 1 ? x.toFixed(3) : x < 100 ? x.toFixed(1) : Math.round(x).toString()
const mb = b => (b / 1048576).toFixed(1)
const out = []
const table = (title, head, cell, note) => {
  out.push(`### ${title}\n`)
  if (note) out.push(note + '\n')
  out.push(`| dead | ${VARIANTS.join(' | ')} |`, `|---|${VARIANTS.map(() => '---:').join('|')}|`)
  for (const d of deads) out.push(`| ${d * 100}% | ${VARIANTS.map(v => cell(v, d)).join(' | ')} |`)
  out.push('')
}

out.push(`## Tombstones vs full reload, N = ${Number(n).toLocaleString('en')}\n`)
out.push('`dead` = share of cells cleared by churn before measuring. Times in ms, warm page cache.\n')
table('Cold column load, number / text', null,
  (v, d) => `${f1(get(v, d, 'load', r => r.prop === 1)?.ms)} / ${f1(get(v, d, 'load', r => r.prop === 2)?.ms)}`)
table('DB size after churn (MB)', null, (v, d) => mb(get(v, d, 'build').bytes))
table('Point set / point delete, one cell per commit (p50 ms)', null,
  (v, d) => `${f1(get(v, d, 'point_set').p50)} / ${f1(get(v, d, 'point_del').p50)}`)
table('Range delete, 10k cells in one commit (ms)', null, (v, d) => f1(get(v, d, 'range_del').ms))
table('Mixed script: 2000 commits, total write time (ms)', null, (v, d) => f1(get(v, d, 'mixed_write').ms))
for (const e of [1, 10, 100, 1000]) {
  table(`Mixed script: reader syncing every ${e} commit${e > 1 ? 's' : ''}, total sync ms (reloads)`, null, (v, d) => {
    const r = get(v, d, 'mixed_sync', r => r.every === e)
    return `${f1(r.sync_ms)}${r.reloads ? ` (${r.reloads})` : ''}`
  }, e === 1 ? 'Script: 90% one-cell set, 8% one-cell delete, 2% delete of 1000 random cells. `full` reloads the column after any delete.' : null)
}
table('Whole column delete: write / reader catch-up (ms)', null,
  (v, d) => { const r = get(v, d, 'column_del'); return `${f1(r.ms)} / ${f1(r.sync_ms)}` })
table('Prune every tombstone: prune ms, VACUUM ms, MB before → after', null, (v, d) => {
  const r = get(v, d, 'prune')
  return v === 'full' ? '—' : `${f1(r.ms)}, ${f1(r.vacuum_ms)}, ${mb(r.bytes_before)} → ${mb(r.bytes_after_vacuum)}`
})
const plans = VARIANTS.map(v => `- \`${v}\`: ${get(v, deads[0], 'build').load_plan}`)
out.push('Load query plans:\n', ...plans, '')
console.log(out.join('\n'))
