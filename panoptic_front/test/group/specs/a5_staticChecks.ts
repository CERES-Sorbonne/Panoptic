/**
 * A5 — a view must not wipe collection state just to draw itself.
 *
 * GridScroller.onMounted used to call manager.clearCustomGroups(true): the emit was what
 * triggered its first compute, and dropping the clusters was how the grid avoided rendering
 * nodes its old row model could not express. That threw away the authored ClusterOverlay map
 * shared with the other pane.
 *
 * Mounting a Vue component headlessly to assert this is more machinery than the check is worth,
 * so it is a static check instead: no component calls the destructive op from a lifecycle hook or
 * a watcher, i.e. as a side effect of drawing. A user-triggered call (a "clear clusters" button's
 * click handler) is fine. The mount now calls computeLines(), which is asserted here too.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

declare const __SRC_DIR__: string

/** Source with // and /* *\/ comments blanked out, so a mention in prose is not a call. */
function stripComments(code: string): string {
    return code
        .replace(/\/\*[\s\S]*?\*\//g, ' ')
        .replace(/(^|[^:])\/\/[^\n]*/g, '$1 ')
}

function vueFiles(dir: string): string[] {
    const out: string[] = []
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) out.push(...vueFiles(full))
        else if (entry.name.endsWith('.vue')) out.push(full)
    }
    return out
}

// Hooks that run because the view is drawn or reacts to state, not because the user asked.
const AUTO_HOOKS = /\b(onBeforeMount|onMounted|onBeforeUpdate|onUpdated|onActivated|onDeactivated|onBeforeUnmount|onUnmounted|watch|watchEffect|watchPostEffect|watchSyncEffect)\s*\(/g

/** The argument text of every lifecycle hook / watcher call, found by paren matching. */
function autoHookBodies(code: string): string[] {
    const bodies: string[] = []
    for (const m of code.matchAll(AUTO_HOOKS)) {
        const start = m.index! + m[0].length
        let depth = 1, i = start
        while (i < code.length && depth > 0) {
            if (code[i] === '(') depth++
            else if (code[i] === ')') depth--
            i++
        }
        bodies.push(code.slice(start, i - 1))
    }
    return bodies
}

const callsClear = (code: string) => autoHookBodies(code).some(b => /clearCustomGroups\s*\(/.test(b))

test('A5: the hook scan sees a mount-time call and ignores a click handler', () => {
    assert.equal(callsClear('onMounted(() => { if (x(1)) props.manager.clearCustomGroups(true) })'), true)
    assert.equal(callsClear('watch(() => a, () => m.clearCustomGroups())'), true)
    assert.equal(callsClear('<div @click="props.collection.clearCustomGroups(true)">'), false)
    assert.equal(callsClear('onMounted(() => computeLines())\nfunction clear() { m.clearCustomGroups(true) }'), false)
})

test('A5: no component calls clearCustomGroups from a lifecycle hook or watcher', () => {
    const components = path.join(__SRC_DIR__, 'components')
    const files = vueFiles(components)
    assert.ok(files.length > 10, 'the static check really found the component tree')
    const offenders = files.filter(f => callsClear(stripComments(fs.readFileSync(f, 'utf8'))))
    assert.deepEqual(offenders.map(f => path.relative(__SRC_DIR__, f)), [],
        'a view is wiping the authored cluster map to draw itself')
})

test('A5: GridScroller.onMounted builds its first layout with computeLines()', () => {
    const file = path.join(__SRC_DIR__, 'components/scrollers/grid/GridScroller.vue')
    const code = stripComments(fs.readFileSync(file, 'utf8'))
    const mount = code.slice(code.indexOf('onMounted('))
    assert.ok(mount.length > 0, 'GridScroller has an onMounted')
    assert.match(mount.slice(0, 400), /computeLines\s*\([^)]*\)/,
        'the mount no longer relies on an emit from a destructive op')
})
