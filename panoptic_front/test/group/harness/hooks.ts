/**
 * Root hooks for the whole suite.
 *
 * Imported first by suite.ts, so they are registered before any spec defines a test:
 *  - every test starts with a clean console capture
 *  - every test fails if ClusterOverlay reported an invariant breach (I1-I5). Those checks only
 *    run in a DEV build, which is why build.mjs pins import.meta.env.DEV to true.
 */
import { beforeEach, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import { resetConsole, invariantBreaches } from './console'

beforeEach(() => { resetConsole() })

afterEach(() => {
    const breaches = invariantBreaches()
    assert.deepEqual(breaches, [], 'ClusterOverlay invariants I1-I5 must hold:\n' + breaches.join('\n'))
})
