'use strict'
/*
 * Wire benchmark — JS side. Decodes the payloads `collection-bench --wire=<dir>` wrote, the way
 * the webview would receive them, under Node (V8) and the macOS `jsc` shell (JavaScriptCore).
 *
 * - stream: today's full-column ingest, as columnStore.requireFullColumn does it: split the
 *   NDJSON, JSON.parse + keysToCamel each line, JSON.parse every value, slotMap lookup,
 *   writeSlot into the column (dates through `new Date(iso)`), buildCSR for tags. Plain
 *   objects instead of the Pinia store, and no requestAnimationFrame yield between chunks,
 *   so this is a lower bound of what the app pays.
 * - window / page / headers: JSON.parse of the text, or a msgpack decode of the bytes with
 *   msgpackr and with @msgpack/msgpack (their browser builds, the same in both engines).
 *
 * Files are read before timing; UTF-8 decoding of the response is not timed (the jsc shell
 * has no TextDecoder), so JSON starts from a string and msgpack from a Uint8Array.
 *
 *   node wire.js --dir=../results/wire-1000000
 *   jsc wire.js -- --dir=../results/wire-1000000
 */

const IS_NODE = typeof process !== 'undefined' && !!(process.versions && process.versions.node)
const ARGV = IS_NODE ? process.argv.slice(2) : Array.from(arguments)
const out = IS_NODE ? (s) => console.log(s) : (s) => print(s)
const now = IS_NODE ? () => performance.now() : () => preciseTime() * 1000
const ENGINE = IS_NODE ? 'v8' : 'jsc'

function arg(name, def) {
    const p = ARGV.find(a => a.startsWith('--' + name + '='))
    return p === undefined ? def : p.slice(name.length + 3)
}
const HERE = IS_NODE ? __dirname : '.'
const DIR = arg('dir', '')
const ONLY = arg('only', '') ? new RegExp(arg('only', '')) : null
if (!DIR) throw new Error('--dir=<wire output dir> is required')

const readText = IS_NODE ? (f) => require('fs').readFileSync(f, 'utf8') : (f) => readFile(f)
const readBytes = IS_NODE ? (f) => new Uint8Array(require('fs').readFileSync(f)) : (f) => readFile(f, 'binary')

// The browser (UMD) builds in both engines, loaded as plain scripts so they set globals.
// The jsc shell has no TextEncoder/TextDecoder: a small UTF-8 stand-in. Both libs only use it
// for strings past a length threshold (msgpackr >= 64 bytes, @msgpack/msgpack > 200 bytes),
// and every string here is shorter, so it is never on the timed path.
if (!IS_NODE && typeof TextDecoder === 'undefined') {
    globalThis.TextEncoder = class { encode(s) { const u = unescape(encodeURIComponent(s)); const b = new Uint8Array(u.length); for (let i = 0; i < u.length; i++) b[i] = u.charCodeAt(i); return b } encodeInto(s, b) { const e = this.encode(s); b.set(e); return { read: s.length, written: e.length } } }
    globalThis.TextDecoder = class { decode(b) { let s = ''; for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]); return decodeURIComponent(escape(s)) } }
}
const loadScript = IS_NODE ? (f) => require('vm').runInThisContext(require('fs').readFileSync(f, 'utf8'), { filename: f }) : load
loadScript(HERE + '/node_modules/msgpackr/dist/index.js')
loadScript(HERE + '/node_modules/@msgpack/msgpack/dist.umd/msgpack.min.js')
const { msgpackr, MessagePack } = globalThis
const unpackr = new msgpackr.Unpackr({ useRecords: false, mapsAsObjects: true, int64AsType: 'number' })
const msgDecoder = new MessagePack.Decoder()

// ── copies of the front code the stream goes through ───────────────────────

// utils.ts keysToCamel / toCamel
const camelCaseCache = {}
function toCamel(s) {
    if (camelCaseCache[s]) return camelCaseCache[s]
    const result = s.replace(/([-_][a-z])/ig, ($1) => $1.toUpperCase().replace('-', '').replace('_', ''))
    camelCaseCache[s] = result
    return result
}
function keysToCamel(o) {
    if (typeof o !== 'object' || o === null) return o
    if (Array.isArray(o)) return o.map(i => keysToCamel(i))
    if (o.constructor === Object) {
        const n = {}
        for (const k in o) {
            if (Object.prototype.hasOwnProperty.call(o, k)) n[toCamel(k)] = keysToCamel(o[k])
        }
        return n
    }
    return o
}

// lib/columns.ts buildCSR
function buildCSR(sparse, count) {
    const offsets = new Int32Array(count + 1)
    let total = 0
    for (let s = 0; s < count; s++) {
        total += sparse[s]?.length ?? 0
        offsets[s + 1] = total
    }
    const values = new Int32Array(total)
    let pos = 0
    for (let s = 0; s < count; s++) {
        const tags = sparse[s]
        if (tags) for (const t of tags) values[pos++] = t
    }
    return { offsets, values }
}

function newColumn(kind, n) {
    switch (kind) {
        case 'numeric': case 'date': return { kind: 'numeric', data: new Float64Array(n).fill(NaN) }
        case 'bool': return { kind: 'bool', data: new Uint8Array(n).fill(255) }
        case 'string': return { kind: 'string', data: new Array(n).fill(null) }
        case 'tag': return { kind: 'tag', sparse: new Array(n).fill(null) }
    }
}

// columnStore.writeSlot for one column
function writeSlot(col, isDate, fetched, slot, value) {
    switch (col.kind) {
        case 'numeric':
            if (isDate && typeof value === 'string') col.data[slot] = value == null ? NaN : new Date(value).getTime()
            else col.data[slot] = value == null ? NaN : Number(value)
            break
        case 'bool':
            col.data[slot] = value == null ? 255 : (value ? 1 : 0)
            break
        case 'string':
            col.data[slot] = value ?? null
            break
        case 'tag':
            col.sparse[slot] = Array.isArray(value) ? value : null
            col.csr = undefined
            break
    }
    fetched[slot] = 1
}

// columnStore.requireFullColumn's apiStreamColumn callback, over the whole response.
function ingestStream(text, propId, kind, n, slotMap) {
    const col = newColumn(kind, n)
    const fetched = new Uint8Array(n)
    const isDate = kind === 'date'
    const progress = { counter: 0, max: 0 }
    let csrBuilt = false
    const parseValue = (v) => typeof v === 'string' ? JSON.parse(v) : v
    for (const line of text.split('\n')) {
        const trimmed = line.trim()
        if (!trimmed) continue
        const data = keysToCamel(JSON.parse(trimmed))
        if (data.state?.maxInstanceValue) progress.max = data.state.maxInstanceValue
        if (data.state?.counterInstanceValue !== undefined) progress.counter = data.state.counterInstanceValue
        if (data.instanceValues) {
            for (const chunk of data.instanceValues) {
                if (chunk.propertyId !== propId) continue
                const ids = chunk.ids || []
                for (let i = 0; i < ids.length; i++) {
                    const slot = slotMap.get(ids[i])
                    if (slot !== undefined) writeSlot(col, isDate, fetched, slot, parseValue(chunk.values[i]))
                }
            }
        }
        if (!csrBuilt && data.instanceValues?.length && col.kind === 'tag') {
            col.csr = buildCSR(col.sparse, n)
            csrBuilt = true
        }
    }
    return col
}

// ── timing ─────────────────────────────────────────────────────────────────

function timeIt(minReps, budgetMs, f) {
    f()
    const times = []
    const t0 = now()
    while (times.length < minReps || now() - t0 < budgetMs) {
        const t = now()
        f()
        times.push(now() - t)
        if (times.length >= 10000) break
    }
    times.sort((a, b) => a - b)
    return { ms: times[times.length >> 1], min_ms: times[0], reps: times.length }
}

function emit(e, extra) {
    out(JSON.stringify({ impl: ENGINE, kind: 'wire', n: MANIFEST.n, group: e.group, op: e.op, fmt: e.fmt, ...extra }))
}

let sink = 0
function touch(v) { sink ^= (typeof v === 'object' && v !== null) ? Object.keys(v).length : 0 }

const MANIFEST = JSON.parse(readText(DIR + '/manifest.json'))
const N = MANIFEST.n
// slot = id - 1, as /instances/base delivers them; built once per project, not per column.
const slotMap = new Map()
for (let s = 0; s < N; s++) slotMap.set(s + 1, s)

for (const e of MANIFEST.files) {
    if (ONLY && !ONLY.test(`${e.group}: ${e.op}`)) continue
    const path = DIR + '/' + e.file
    if (e.group === 'stream') {
        const text = readText(path)
        const t = timeIt(N >= 5000000 ? 2 : 3, 0, () => touch(ingestStream(text, e.prop, e.col_kind, N, slotMap)))
        emit(e, { lib: 'columnStore', ...t })
    } else if (e.fmt === 'json') {
        const text = readText(path)
        emit(e, { lib: 'JSON.parse', ...timeIt(200, 300, () => touch(JSON.parse(text))) })
    } else {
        const bytes = readBytes(path)
        // Same value as the JSON twin, with both decoders.
        const want = JSON.stringify(JSON.parse(readText(path.replace(/\.msgpack$/, '.json'))))
        const same = (v) => JSON.stringify(v) === want
        emit(e, { lib: 'msgpackr', same: same(unpackr.unpack(bytes)), ...timeIt(200, 300, () => touch(unpackr.unpack(bytes))) })
        emit(e, { lib: '@msgpack/msgpack', same: same(msgDecoder.decode(bytes)), ...timeIt(200, 300, () => touch(msgDecoder.decode(bytes))) })
    }
}
if (sink === 0.5) out('')
