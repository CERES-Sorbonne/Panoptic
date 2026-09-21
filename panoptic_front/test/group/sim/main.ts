/**
 * `npm run test:sim` — the standalone simulation.
 *
 *   SIM_SEED=<n>        replay one run exactly (runs defaults to 1 when it is set)
 *   SIM_RUNS=<n>        number of runs            (default 150)
 *   SIM_STEPS=<n>       operations per run        (default 400)
 *   SIM_INSTANCES=<n>   instances in the fixture  (default: a 6 / 16 / 40 / 90 rotation)
 *   SIM_SHRINK_MS=<n>   shrink budget per failure (default 8000, 0 to disable)
 *   SIM_QUIET=1         only the summary and the failures
 */
import { simulate, formatFailure } from './runner'

const env = (name: string): string | undefined => process.env[name]

function num(name: string, fallback: number): number {
    const raw = env(name)
    if (raw === undefined || raw === '') return fallback
    const v = Number(raw)
    return Number.isFinite(v) ? Math.trunc(v) : fallback
}

const seedGiven = env('SIM_SEED') !== undefined && env('SIM_SEED') !== ''
const seed = num('SIM_SEED', (Date.now() ^ (Math.random() * 0xffffffff)) | 0)
const runs = num('SIM_RUNS', seedGiven ? 1 : 150)
const steps = num('SIM_STEPS', 400)
// A tiny collection and a big one break different things, so the runs cycle through sizes
// unless one is asked for.
const sizeGiven = env('SIM_INSTANCES') !== undefined && env('SIM_INSTANCES') !== ''
const instances: number | number[] = sizeGiven ? num('SIM_INSTANCES', 40) : [6, 16, 40, 90]
const shrinkMs = num('SIM_SHRINK_MS', 8000)
const quiet = env('SIM_QUIET') === '1'

console.log(`group simulation — base seed ${seed}, ${runs} run(s) x ${steps} step(s), `
    + `${Array.isArray(instances) ? instances.join('/') : instances} instances, shrink budget ${shrinkMs}ms`)
console.log(`replay this batch with: SIM_SEED=${seed} SIM_RUNS=${runs} SIM_STEPS=${steps}`
    + `${sizeGiven ? ` SIM_INSTANCES=${instances}` : ''} npm run test:sim`)
console.log('')

const report = await simulate({
    seed, runs, steps, instances, shrinkMs,
    onRun(index, runSeed, size, result) {
        if (quiet && result.failedAt === undefined) return
        const state = result.failedAt === undefined
            ? `ok    ${String(result.log.length).padStart(4)} ops`
            : `FAIL  at op ${result.failedAt} (${result.op})`
        console.log(`  run ${String(index + 1).padStart(3)}/${runs}  seed ${String(runSeed).padStart(12)}  `
            + `n=${String(size).padStart(3)}  ${state}`)
    },
})

console.log('')
console.log(`${report.opsApplied} operations applied in ${(report.ms / 1000).toFixed(1)}s, `
    + `${report.failures.length} failing run(s)`)
if (!quiet) {
    const counts = [...report.histogram.entries()].sort((a, b) => b[1] - a[1])
    console.log('operation mix: ' + counts.map(([name, n]) => `${name}=${n}`).join('  '))
}

if (report.failures.length) {
    console.log('')
    for (const failure of report.failures) {
        console.log(formatFailure(failure))
        console.log('')
    }
    process.exitCode = 1
} else {
    console.log('every invariant held after every operation.')
}
