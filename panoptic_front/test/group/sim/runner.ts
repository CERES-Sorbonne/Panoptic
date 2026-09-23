/**
 * The runner: sample a run, check after every step, and on a failure shrink the operation log
 * to the shortest sequence that still breaks the same invariant.
 *
 * A run is fully described by its seed — the dataset, the operations and their parameters all
 * come out of it — so `SIM_SEED=<n>` reproduces one exactly. Shrinking replays the RECORDED
 * plans instead of re-sampling: a plan names its targets by position among the current
 * candidates, so dropping an operation leaves the rest executable and the replay deterministic.
 */
import { resetConsole } from '../harness/console'
import { Rng } from './rng'
import { World, createWorld } from './world'
import { Plan, Op, OP_BY_NAME, pickOp, describe } from './ops'
import { checkAll, Problem } from './check'

export interface RunResult {
    seed: number
    /** Operations actually applied. */
    log: Plan[]
    /** Index into `log` of the step that failed; -1 for the initial state, undefined when clean. */
    failedAt?: number
    op?: string
    problems?: Problem[]
}

export interface SimOptions {
    seed: number
    runs: number
    steps: number
    /** One size, or a rotation the runs cycle through — a tiny collection and a big one break
     *  different things. */
    instances: number | number[]
    /** Wall-clock budget for shrinking one failure, in ms. 0 disables shrinking. */
    shrinkMs?: number
    onRun?: (index: number, seed: number, instances: number, result: RunResult) => void
}

export interface Failure {
    seed: number
    /** The fixture size this run used, so the replay line is complete. */
    instances: number
    step: number
    op: string
    problems: Problem[]
    /** The full log up to and including the failing step. */
    log: Plan[]
    /** The shortest replayable log found that breaks the same invariant. */
    minimal: Plan[]
    shrunk: boolean
}

export interface SimReport {
    seed: number
    runs: number
    steps: number
    opsApplied: number
    /** How often each operation actually ran — the answer to "is this simulation vacuous?". */
    histogram: Map<string, number>
    failures: Failure[]
    ms: number
}

/** The invariant family a failure belongs to — what "the same bug" means while shrinking. */
export function categoryOf(r: RunResult): string {
    return r.problems?.[0]?.tag ?? 'none'
}

/**
 * Run one sequence. With `fixed` the recorded plans are replayed in order; without it the
 * operations are sampled from the run's own RNG.
 */
export async function runSequence(seed: number, instances: number, steps: number, fixed?: Plan[]): Promise<RunResult> {
    const rng = new Rng(seed)
    let w: World
    try {
        w = await createWorld(rng, { instances })
    } catch (e) {
        return { seed, log: [], failedAt: -1, op: '<setup>', problems: [{ tag: 'throw', msg: errText(e) }] }
    }

    const initial = checkAll(w)
    if (initial.length) return { seed, log: [], failedAt: -1, op: '<initial state>', problems: initial }

    const log: Plan[] = []
    const total = fixed ? fixed.length : steps
    for (let i = 0; i < total; i++) {
        let plan: Plan | null = null
        let op: Op | undefined
        if (fixed) {
            plan = fixed[i]
            op = OP_BY_NAME.get(plan.op)
            if (!op) continue
        } else {
            for (let tries = 0; tries < 8 && !plan; tries++) {
                op = pickOp(rng)
                plan = op.plan(w, rng)
            }
            if (!plan || !op) continue
        }
        log.push(plan)
        // The DEV cluster invariants report through console.error; clear the capture so what is
        // left afterwards belongs to this step.
        resetConsole()
        try {
            await op.apply(w, plan)
        } catch (e) {
            return { seed, log, failedAt: log.length - 1, op: plan.op, problems: [{ tag: 'throw', msg: errText(e) }] }
        }
        const problems = checkAll(w)
        if (problems.length) return { seed, log, failedAt: log.length - 1, op: plan.op, problems }
    }
    return { seed, log }
}

function errText(e: unknown): string {
    const err = e as any
    return String(err?.stack ?? err)
}

/**
 * Delta-debugging over the op log: try removing ever finer chunks, keeping any removal that
 * still breaks the same invariant family. Bounded by wall clock, because every candidate is a
 * full replay.
 */
export async function shrinkLog(seed: number, instances: number, log: Plan[], tag: string, budgetMs: number): Promise<Plan[]> {
    const deadline = Date.now() + budgetMs
    let best = log
    let n = 2
    while (best.length > 1 && Date.now() < deadline) {
        const chunk = Math.ceil(best.length / n)
        let reduced = false
        for (let i = 0; i < best.length; i += chunk) {
            if (Date.now() >= deadline) break
            const cand = best.slice(0, i).concat(best.slice(i + chunk))
            if (!cand.length) continue
            const r = await runSequence(seed, instances, 0, cand)
            if (r.failedAt !== undefined && r.failedAt >= 0 && categoryOf(r) === tag) {
                best = cand.slice(0, r.failedAt + 1)
                reduced = true
                break
            }
        }
        if (reduced) { n = Math.max(2, n - 1); continue }
        if (n >= best.length) break
        n = Math.min(n * 2, best.length)
    }
    return best
}

/** Run the whole batch. Each run gets its own seed, printed by the caller. */
export async function simulate(opts: SimOptions): Promise<SimReport> {
    const started = Date.now()
    const failures: Failure[] = []
    const histogram = new Map<string, number>()
    let opsApplied = 0

    const sizes = Array.isArray(opts.instances) ? opts.instances : [opts.instances]
    for (let i = 0; i < opts.runs; i++) {
        const seed = (opts.seed + i) | 0
        const instances = sizes[i % sizes.length]
        const result = await runSequence(seed, instances, opts.steps)
        opsApplied += result.log.length
        for (const plan of result.log) histogram.set(plan.op, (histogram.get(plan.op) ?? 0) + 1)
        opts.onRun?.(i, seed, instances, result)
        if (result.failedAt === undefined) continue

        const tag = categoryOf(result)
        const budget = opts.shrinkMs ?? 8000
        const minimal = budget > 0 && result.log.length > 1
            ? await shrinkLog(seed, instances, result.log, tag, budget)
            : result.log
        // Report what the MINIMAL log breaks, not what the full one did: the shorter sequence is
        // the repro, so its findings are the ones to read.
        const shrunk = minimal.length < result.log.length
        const final = shrunk ? await runSequence(seed, instances, 0, minimal) : result
        failures.push({
            seed,
            instances,
            step: final.failedAt ?? result.failedAt,
            op: final.op ?? result.op ?? '?',
            problems: (final.problems?.length ? final.problems : result.problems) ?? [],
            log: result.log,
            minimal,
            shrunk,
        })
    }

    return { seed: opts.seed, runs: opts.runs, steps: opts.steps, opsApplied, histogram, failures, ms: Date.now() - started }
}

/** A failure, written out so it can be pasted into a bug report and replayed. */
export function formatFailure(f: Failure): string {
    const lines: string[] = []
    lines.push(`FAILURE  seed=${f.seed}  instances=${f.instances}  step=${f.step}  op=${f.op}`)
    lines.push(`  replay:  SIM_SEED=${f.seed} SIM_RUNS=1 SIM_INSTANCES=${f.instances} npm run test:sim`)
    lines.push(`  broken invariants:`)
    for (const problem of f.problems.slice(0, 8)) lines.push(`    [${problem.tag}] ${problem.msg}`)
    if (f.problems.length > 8) lines.push(`    … and ${f.problems.length - 8} more`)
    lines.push(`  ${f.shrunk ? 'minimal' : 'full'} op log (${f.minimal.length} of ${f.log.length} ops):`)
    f.minimal.forEach((plan, i) => lines.push(`    ${String(i).padStart(3)}  ${describe(plan)}`))
    return lines.join('\n')
}
