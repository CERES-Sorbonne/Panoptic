// Memory benchmark: runs every op once per engine, each in its own process under `memwatch`
// (rust/src/bin/memwatch.rs), and joins three numbers per op into results/mem-<n>.jsonl + a
// markdown report:
//   - retained: live heap bytes the result keeps alive (in-process, after a full GC; for Rust,
//     the counting allocator). Group ops keep the GroupManager's result, as in the app.
//   - peak: highest process memory footprint (what Activity Monitor shows) during the op, minus the
//     footprint once the data is loaded. It includes freed-but-not-returned heap and GC slack.
//   - Rust heap peak: the counting allocator's exact high-water mark during the op.
// The data load itself is reported as live bytes and as the process footprint once loaded.
//
//   node mem.js 1000000                       all engines
//   node mem.js 1000000 --engines=rust-1t,v8  a subset
//   node mem.js 1000000 --report              only print the report from results/mem-<n>.jsonl
const fs = require('fs'), path = require('path'), os = require('os')
const { execFileSync, spawnSync } = require('child_process')

const DIR = __dirname
const N = Number(process.argv[2] || 1000000)
const flag = (name) => process.argv.find(a => a.startsWith(`--${name}=`))?.slice(name.length + 3)
const NM = path.resolve(DIR, '../../panoptic_front/node_modules')
const JSC = '/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc'
const RUST = path.join(DIR, 'rust/target/release/collection-bench')
const MEMWATCH = path.join(DIR, 'rust/target/release/memwatch')
const BENCH = path.join(DIR, 'js/bench.js')
const NODE = ['node', '--expose-gc', '--max-old-space-size=14000']
const OUT = path.join(DIR, 'results', `mem-${N}.jsonl`)
const CPUS = os.availableParallelism()

const ENGINES = {
    'v8':      [...NODE, BENCH, `--nm=${NM}`],
    'jsc':     [JSC, BENCH, '--', `--nm=${NM}`],
    'v8-raw':  [...NODE, BENCH, '--store=raw'],
    'rust-1t': [RUST, '--threads=1'],
    [`rust-${CPUS}t`]: [RUST, `--threads=${CPUS}`],
}

function run(cmd, op) {
    const p = spawnSync(MEMWATCH, [...cmd, `--n=${N}`, '--mem', `--op=${op}`], { encoding: 'utf8', maxBuffer: 1 << 26 })
    if (p.status !== 0) throw new Error(`${cmd.join(' ')} --op=${op} failed:\n${p.stderr}`)
    const lines = p.stdout.trim().split('\n').filter(Boolean).map(JSON.parse)
    const w = lines.find(l => l.memwatch)
    return { meta: lines.find(l => l.meta), row: lines.find(l => !l.meta && !l.memwatch), load: w.load_footprint, peak: w.peak_footprint - w.load_footprint }
}

function measure() {
    execFileSync('cargo', ['build', '--release', '-q'], { cwd: path.join(DIR, 'rust'), stdio: 'inherit' })
    const ops = execFileSync(RUST, ['--list'], { encoding: 'utf8' }).trim().split('\n')
    const names = (flag('engines') ?? Object.keys(ENGINES).join(',')).split(',')
    if (names.includes('jsc') && !fs.existsSync(JSC)) names.splice(names.indexOf('jsc'), 1)
    fs.mkdirSync(path.dirname(OUT), { recursive: true })
    const rows = fs.existsSync(OUT) ? fs.readFileSync(OUT, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse).filter(r => !names.includes(r.impl)) : []
    for (const impl of names) {
        const cmd = ENGINES[impl]
        process.stderr.write(`${impl}: load`)
        const load = run(cmd, '__load_only__')
        rows.push({ impl, n: N, load: true, live_bytes: load.meta.live_bytes, footprint: load.load })
        for (const op of ops) {
            process.stderr.write(` · ${op.split(': ')[1]}`)
            const r = run(cmd, op)
            rows.push({ ...r.row, impl, footprint: r.load, peak_footprint: r.peak })
        }
        process.stderr.write('\n')
        fs.writeFileSync(OUT, rows.map(r => JSON.stringify(r)).join('\n') + '\n')
    }
}

function report() {
    const rows = fs.readFileSync(OUT, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse)
    const order = ['v8', 'jsc', 'v8-raw', 'rust-1t']
    const impls = [...new Set(rows.map(r => r.impl))].sort((a, b) => (order.indexOf(a) + 1 || 99) - (order.indexOf(b) + 1 || 99))
    const rusts = impls.filter(i => i.startsWith('rust-'))
    const js = impls.filter(i => !i.startsWith('rust-'))
    const ops = [...new Set(rows.filter(r => !r.load).map(r => r.kind + ': ' + r.op))]
    const get = (impl, op) => rows.find(r => r.impl === impl && (op ? !r.load && r.kind + ': ' + r.op === op : r.load))
    const MB = (b) => b == null ? '—' : b < 0.05 * 2 ** 20 ? '~0' : (b / 2 ** 20 >= 100 ? (b / 2 ** 20).toFixed(0) : (b / 2 ** 20).toFixed(1)) + ' MB'
    const x = (a, b) => a == null || b == null || b < 0.05 * 2 ** 20 ? '—' : (a / b >= 10 ? (a / b).toFixed(0) : (a / b).toFixed(1)) + '×'
    const table = (head, lines) => [
        '| ' + head.join(' | ') + ' |',
        '|' + head.map((_, i) => i ? '---:' : '---').join('|') + '|',
        ...lines.map(l => '| ' + l.join(' | ') + ' |'),
    ].join('\n')
    const r1 = 'rust-1t'
    const sigs = (op) => new Set(impls.map(i => get(i, op)).filter(Boolean).map(r => `${r.count}/${r.entries}/${r.hash}`)).size === 1 ? 'yes' : 'NO'

    const lines = [`\nN = ${N.toLocaleString('en')}  (MB = 2^20 bytes)\n`, '### Loaded columns\n']
    lines.push(table(['', ...impls], [
        ['live data (heap after GC)', ...impls.map(i => MB(get(i)?.live_bytes))],
        ['process footprint once loaded', ...impls.map(i => MB(get(i)?.footprint))],
    ]))
    lines.push('\n### Retained by the result (live heap after GC, result held)\n')
    lines.push(table(['op', ...js, r1, `v8 vs ${r1}`, `jsc vs ${r1}`, 'same result'],
        ops.map(op => [op, ...js.map(i => MB(get(i, op)?.retained_bytes)), MB(get(r1, op)?.retained_bytes),
            x(get('v8', op)?.retained_bytes, get(r1, op)?.retained_bytes), x(get('jsc', op)?.retained_bytes, get(r1, op)?.retained_bytes), sigs(op)])))
    lines.push('\n### Peak during the op (process footprint above the footprint once loaded)\n')
    lines.push(table(['op', ...impls, ...rusts.map(i => `${i} heap peak`)],
        ops.map(op => [op, ...impls.map(i => MB(get(i, op)?.peak_footprint)), ...rusts.map(i => MB(get(i, op)?.peak_bytes))])))
    const max = (i, k) => Math.max(...ops.map(op => get(i, op)?.[k] ?? 0))
    lines.push('| **max** | ' + [...impls.map(i => `**${MB(max(i, 'peak_footprint'))}**`), ...rusts.map(i => `**${MB(max(i, 'peak_bytes'))}**`)].join(' | ') + ' |')
    const text = lines.join('\n') + '\n'
    fs.writeFileSync(path.join(DIR, 'results', `mem-report-${N}.md`), text)
    console.log(text)
}

if (!process.argv.includes('--report')) measure()
report()
