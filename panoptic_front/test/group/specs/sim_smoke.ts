/**
 * The simulation, as a fixed-seed smoke run inside the fast suite.
 *
 * The real thing is `npm run test:sim` (hundreds of operations over dozens of seeds). This is
 * the same machinery on one pinned seed and a short budget, so a change that makes the model or
 * the harness itself stop working is caught by `npm test` rather than only by the nightly-sized
 * run. See ../sim/ for what it covers.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { simulate, formatFailure } from '../sim/runner'
import { resetConsole } from '../harness/console'

const SEED = 0x5117_0000
const RUNS = 3
const STEPS = 50
const INSTANCES = 24

test(`sim: ${RUNS} runs x ${STEPS} ops keep every invariant (seed ${SEED})`, async () => {
    const report = await simulate({ seed: SEED, runs: RUNS, steps: STEPS, instances: INSTANCES, shrinkMs: 0 })
    // The simulation clears the console capture per step; a failure is reported through its own
    // channel, so leave the capture clean for the afterEach hook either way.
    resetConsole()
    assert.deepEqual(
        report.failures.map(f => formatFailure(f)),
        [],
        'the simulation found an invariant breach',
    )
})
