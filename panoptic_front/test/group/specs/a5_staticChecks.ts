/**
 * A5 — a view must not wipe collection state just to draw itself.
 *
 * GridScroller.onMounted used to call manager.clearCustomGroups(true): the emit was what
 * triggered its first compute, and dropping the clusters was how the grid avoided rendering
 * nodes its old row model could not express. That threw away the authored ClusterOverlay map
 * shared with the other pane.
 *
 * Mounting a Vue component headlessly to assert this is more machinery than the check is worth,
 * so it is a static check instead: no component calls the destructive op at all. The mount now
 * calls computeLines(), which is asserted here too.
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

test('A5: no component calls clearCustomGroups', () => {
    const components = path.join(__SRC_DIR__, 'components')
    const files = vueFiles(components)
    assert.ok(files.length > 10, 'the static check really found the component tree')
    const offenders = files.filter(f => /clearCustomGroups\s*\(/.test(stripComments(fs.readFileSync(f, 'utf8'))))
    assert.deepEqual(offenders.map(f => path.relative(__SRC_DIR__, f)), [],
        'a view is wiping the authored cluster map to draw itself')
})

test('A5: GridScroller.onMounted builds its first window with computeLines()', () => {
    const file = path.join(__SRC_DIR__, 'components/scrollers/grid/GridScroller.vue')
    const code = stripComments(fs.readFileSync(file, 'utf8'))
    const mount = code.slice(code.indexOf('onMounted('))
    assert.ok(mount.length > 0, 'GridScroller has an onMounted')
    assert.match(mount.slice(0, 400), /computeLines\s*\(\s*\)/,
        'the mount no longer relies on an emit from a destructive op')
})
