/**
 * Console capture.
 *
 * ClusterOverlay.checkInvariants (I1-I5) runs only in a DEV build and reports through
 * console.error, so the suite runs with import.meta.env.DEV on and treats any such line as a
 * failure. cluster() and computeSha1Piles report through console.warn; those are captured too,
 * because several tests assert on them, and kept out of the transcript either way.
 */

const realLog = console.log

let breaches: string[] = []
let otherErrors: string[] = []
let warnings: string[] = []

console.error = (...args: any[]) => {
    const msg = args.map(String).join(' ')
    // Nothing is forwarded: ClusterManager logs a failed run through console.error and the
    // A11 spec provokes one on purpose. Everything is readable through capturedErrors().
    if (msg.includes('[ClusterOverlay]')) breaches.push(msg)
    else otherErrors.push(msg)
}
console.warn = (...args: any[]) => { warnings.push(args.map(String).join(' ')) }
// grpLog is on in a DEV build unless window.__grpDebug says otherwise (build.mjs sets it
// false), so nothing should reach console.log; keep the real one for the reporter.
console.log = realLog

/** Forget everything captured so far. Called at the start of each test. */
export function resetConsole() {
    breaches = []
    otherErrors = []
    warnings = []
}

/** ClusterOverlay invariant breaches (I1-I5) seen since the last reset. */
export function invariantBreaches(): string[] { return breaches }
/** console.warn lines seen since the last reset. */
export function capturedWarnings(): string[] { return warnings }
export function capturedErrors(): string[] { return otherErrors }
