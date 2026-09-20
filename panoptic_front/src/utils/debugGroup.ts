/**
 * Temporary grouping diagnostics, for tracing a value edit from the data delta through to the
 * group tree. On by default; turn it off in the console with `window.__grpDebug = false`.
 *
 * Remove once the tag-removal regrouping issue is settled.
 */

export function grpDebugOn(): boolean {
    return (window as any).__grpDebug !== false
}

export function grpLog(tag: string, data?: any) {
    if (!grpDebugOn()) return
    if (data === undefined) console.log('%c[grp]%c ' + tag, 'color:#2E4FD0;font-weight:700', '')
    else console.log('%c[grp]%c ' + tag, 'color:#2E4FD0;font-weight:700', '', data)
}

// Sets are unreadable in the console once they hold thousands of ids.
export function few<T>(it: Iterable<T> | undefined, n = 20): T[] {
    if (!it) return []
    const out: T[] = []
    for (const v of it) { out.push(v); if (out.length >= n) break }
    return out
}

// The instances the current update is about. Set once by GroupManager before it hands the
// update to the cluster layer, so the overlay can report what happened to exactly those slots
// without threading the set through every call.
let focus: number[] = []

export function grpSetFocus(ids: Iterable<number>) {
    focus = grpDebugOn() ? few(ids, 5) : []
}

export function grpFocus(): number[] {
    return focus
}
