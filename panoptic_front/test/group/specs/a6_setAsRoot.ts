/**
 * A6 — setAsRoot is gone.
 *
 * It pushed a foreign group in as the tree root, which every reader of the (non-reactive) tree
 * then had to defend against. The views build their own manager instead. This test exists so it
 * cannot be reintroduced unnoticed.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { GroupManager } from '@/core/GroupManager'

test('A6: GroupManager has no setAsRoot', () => {
    assert.equal((GroupManager.prototype as any).setAsRoot, undefined,
        'setAsRoot is back on the prototype')
    assert.equal('setAsRoot' in GroupManager.prototype, false)
    assert.equal('setAsRoot' in (new GroupManager() as any), false)
})
