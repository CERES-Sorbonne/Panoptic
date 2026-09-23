/**
 * Headless stand-in for @/data/stores/actionStore. The result of the next executeAction is
 * settable, so a cluster run can be made to succeed, come back empty, or throw — and, with
 * `defer`, to stay in flight until the test releases it, which is how the tree gets rebuilt
 * under a running clustering.
 */
export const actionStub = {
    next: [] as any[],
    throws: false,
    /** One-shot: the NEXT executeAction hangs until releaseAction is called. */
    defer: false,
}

let waiting: ((value: any) => void) | undefined

export function resetAction() {
    actionStub.next = []
    actionStub.throws = false
    actionStub.defer = false
    waiting = undefined
}

/** Answer the deferred call with these groups. */
export function releaseAction(groups: any[]) {
    const resolve = waiting
    waiting = undefined
    resolve?.({ groups })
}

export function isActionPending() { return waiting !== undefined }

export function useActionStore() {
    return {
        async executeAction() {
            if (actionStub.throws) throw new Error('action failed')
            if (actionStub.defer) {
                actionStub.defer = false
                return await new Promise(resolve => { waiting = resolve })
            }
            return { groups: actionStub.next }
        },
    } as any
}
