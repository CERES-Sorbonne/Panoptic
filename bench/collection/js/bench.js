'use strict'
/*
 * Collection benchmark — JS side.
 *
 * A stripped-down copy of the hot paths of FilterManager / SortManager / GroupManager
 * (panoptic_front/src/core), run on synthetic columns laid out exactly like columnStore
 * (Float64Array numeric/date, Uint8Array bool with 255 = null, (string|null)[] strings,
 * (number[]|null)[] sparse tags). Everything that is not data work (Vue state, events,
 * column downloads, clusters, plugin queries, incremental updates) is left out.
 *
 * --store=pinia (default) builds the column store with the real Pinia + Vue from
 * panoptic_front/node_modules, so every per-slot `col.readSlot(...)` pays the same
 * reactive-proxy get + Pinia action wrapper it pays in the app. --store=raw uses a plain
 * object: what the same algorithms cost without the store overhead.
 *
 * Runs under Node (V8) and the macOS `jsc` shell (JavaScriptCore = the Tauri webview on macOS).
 * Data is generated with the same PRNG as the Rust side; every op prints a checksum so the
 * two implementations can be checked to produce identical results.
 *
 *   node --expose-gc --max-old-space-size=12288 bench.js --n=1000000
 *   jsc bench.js -- --n=1000000
 */

// ── environment shim (node / jsc) ──────────────────────────────────────────

const IS_NODE = typeof process !== 'undefined' && !!(process.versions && process.versions.node)
const ARGV = IS_NODE ? process.argv.slice(2) : Array.from(arguments)
const out = IS_NODE ? (s) => console.log(s) : (s) => print(s)
const now = IS_NODE ? () => performance.now() : () => preciseTime() * 1000
const doGC = typeof gc === 'function' ? gc : (typeof globalThis.gc === 'function' ? globalThis.gc : () => {})
const ENGINE = IS_NODE ? 'v8' : 'jsc'

function arg(name, def) {
    const p = ARGV.find(a => a.startsWith('--' + name + '='))
    return p === undefined ? def : p.slice(name.length + 3)
}
const N = Number(arg('n', 1000000))
const REPS = Number(arg('reps', N >= 5000000 ? 3 : 5))
const WARMUP = Number(arg('warmup', 1))
const STORE = arg('store', 'pinia')
const ONLY = arg('only', '') ? new RegExp(arg('only', '')) : null
const SKIP = arg('skip', '') ? new RegExp(arg('skip', '')) : null
const NM = arg('nm', '../../../panoptic_front/node_modules')
// --mem: one run per op, reporting live heap bytes (after a full GC) retained by the result.
const MEM = ARGV.includes('--mem')
const OP = arg('op', '')

// Live JS heap + ArrayBuffer backing stores after a full GC (jsc's fullGC() counts both).
function liveBytes() {
    if (!IS_NODE) return fullGC()
    doGC()
    const u = process.memoryUsage()
    return u.heapUsed + u.arrayBuffers
}

let VueLib = null, PiniaLib = null
if (STORE === 'pinia') {
    if (IS_NODE) {
        process.env.NODE_ENV = 'production'
        const path = require('path')
        const nm = path.resolve(__dirname, NM)
        VueLib = require(nm + '/vue')
        PiniaLib = require(nm + '/pinia')
    } else {
        globalThis.window = globalThis
        globalThis.process = { env: { NODE_ENV: 'production' } }
        load(NM + '/vue/dist/vue.runtime.global.prod.js')
        load(NM + '/vue-demi/lib/index.iife.js')
        load(NM + '/pinia/dist/pinia.iife.prod.js')
        VueLib = globalThis.Vue
        PiniaLib = globalThis.Pinia
    }
    PiniaLib.setActivePinia(PiniaLib.createPinia())
}

// ── deterministic data (mirrors rust/src/data.rs) ──────────────────────────

function mulberry32(seed) {
    let a = seed | 0
    const next = () => {
        a = (a + 0x6D2B79F5) | 0
        let t = a
        t = Math.imul(t ^ (t >>> 15), t | 1)
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296
    }
    next.int = (k) => Math.floor(next() * k)
    return next
}

const SYL = ['ka', 'ro', 'mi', 'ta', 'ne', 'so', 'lu', 'vi', 'po', 'de', 'ga', 'fi', 'zu', 'be', 'xo', 'qui',
    'ar', 'el', 'on', 'us', 'ix', 'ya', 'we', 'jo', 'ha', 'ci', 'mo', 'ru', 'sa', 'te', 'li', 'no']
const N_WORDS = 2000, N_LABELS = 300, N_TAGS = 1000
const DATE_BASE = Date.UTC(2015, 0, 1), DATE_SPAN = 10 * 365.25 * 86400000

const PropertyType = {
    string: 'string', number: 'number', date: 'date', checkbox: 'checkbox',
    multi_tags: 'multi_tags', tag: 'tag', path: 'path', url: 'url', color: 'color',
    _id: '_id', _width: '_width', _height: '_height', _sha1: '_sha1', _ahash: '_ahash', _folders: '_folders',
}
const P = { text: 1, label: 2, number: 3, score: 4, date: 5, check: 6, tags: 7 }

function generate(n) {
    const t0 = now()
    let r = mulberry32(1)
    const words = [], seen = new Set()
    while (words.length < N_WORDS) {
        const len = 2 + r.int(3), parts = []
        for (let j = 0; j < len; j++) parts.push(SYL[r.int(32)])
        const w = parts.join('')
        if (!seen.has(w)) { seen.add(w); words.push(w) }
    }

    const text = new Array(n)
    r = mulberry32(2)
    for (let i = 0; i < n; i++) {
        if (r() < 0.08) { text[i] = null; continue }
        const a = words[r.int(N_WORDS)], b = words[r.int(N_WORDS)], c = words[r.int(N_WORDS)], num = r.int(10000)
        text[i] = [a[0].toUpperCase() + a.slice(1), b, c, num + '.jpg'].join('_')
    }
    const label = new Array(n)
    r = mulberry32(3)
    for (let i = 0; i < n; i++) label[i] = r() < 0.1 ? null : words[r.int(N_LABELS)]

    const number = new Float64Array(n)
    r = mulberry32(4)
    for (let i = 0; i < n; i++) number[i] = r() < 0.05 ? NaN : r.int(10000)
    const score = new Float64Array(n)
    r = mulberry32(5)
    for (let i = 0; i < n; i++) score[i] = r() < 0.05 ? NaN : r() * 1000
    const date = new Float64Array(n)
    r = mulberry32(6)
    for (let i = 0; i < n; i++) date[i] = r() < 0.05 ? NaN : DATE_BASE + Math.floor(r() * DATE_SPAN)
    const check = new Uint8Array(n)
    r = mulberry32(7)
    for (let i = 0; i < n; i++) check[i] = r() < 0.1 ? 255 : (r() < 0.5 ? 1 : 0)

    // Tag registry: ids 1..N_TAGS, ~60% of ids > 50 hang under an earlier tag.
    r = mulberry32(9)
    const parent = new Int32Array(N_TAGS + 1)
    for (let id = 1; id <= N_TAGS; id++) parent[id] = (id > 50 && r() < 0.6) ? 1 + r.int(id - 1) : 0
    const tags = {}
    for (let id = 1; id <= N_TAGS; id++) {
        const allParents = []
        for (let p = parent[id]; p; p = parent[p]) allParents.push(p)
        tags[id] = { id, value: words[N_WORDS - N_TAGS + id - 1], parents: parent[id] ? [parent[id]] : [], allParents, allChildren: [] }
    }
    for (let id = 1; id <= N_TAGS; id++) for (const p of tags[id].allParents) tags[p].allChildren.push(id)

    const tagCol = new Array(n)
    r = mulberry32(8)
    for (let i = 0; i < n; i++) {
        const k = r.int(6), arr = []
        for (let j = 0; j < k; j++) {
            const x = r()
            const id = 1 + Math.floor(x * x * N_TAGS)
            if (!arr.includes(id)) arr.push(id)
        }
        tagCol[i] = arr.length ? arr : null
    }

    const ids = new Int32Array(n)
    for (let i = 0; i < n; i++) ids[i] = i + 1

    const properties = {
        [P.text]:   { id: P.text,   type: PropertyType.string, name: 'text' },
        [P.label]:  { id: P.label,  type: PropertyType.string, name: 'label' },
        [P.number]: { id: P.number, type: PropertyType.number, name: 'number' },
        [P.score]:  { id: P.score,  type: PropertyType.number, name: 'score' },
        [P.date]:   { id: P.date,   type: PropertyType.date,   name: 'date' },
        [P.check]:  { id: P.check,  type: PropertyType.checkbox, name: 'check' },
        [P.tags]:   { id: P.tags,   type: PropertyType.multi_tags, name: 'tags', tags },
    }
    const columns = {
        [P.text]:   { kind: 'string', data: text },
        [P.label]:  { kind: 'string', data: label },
        [P.number]: { kind: 'numeric', data: number },
        [P.score]:  { kind: 'numeric', data: score },
        [P.date]:   { kind: 'numeric', data: date },
        [P.check]:  { kind: 'bool', data: check },
        [P.tags]:   { kind: 'tag', sparse: tagCol },
    }
    const propTypes = {}
    for (const p of Object.values(properties)) propTypes[p.id] = p.type
    return { words, properties, tags, columns, propTypes, ids, genMs: now() - t0 }
}

// ── column store stand-in (columnStore.ts getRawBuffer / readSlot) ─────────

let useColumnStore, DATA

function setupColumnStore(D) {
    const columnData = D.columns
    const _propTypes = D.propTypes
    const instanceIdsArr = D.ids
    const _instanceIdPropId = 100, _sha1PropId = 101, _fileIdPropId = 102
    const sha1s = [], fileIds = new Int32Array(0)
    const setup = () => {
        function getRawBuffer(propId) {
            if (propId === null) return undefined
            if (propId === _instanceIdPropId) return instanceIdsArr
            if (propId === _sha1PropId) return sha1s
            if (propId === _fileIdPropId) return fileIds
            const col = columnData[propId]
            if (!col) return undefined
            return col.kind === 'tag' ? col.sparse : col.data
        }
        function readSlot(propId, slot) {
            if (propId === _instanceIdPropId) return isNaN(instanceIdsArr[slot]) ? null : instanceIdsArr[slot]
            if (propId === _sha1PropId) return sha1s[slot]
            if (propId === _fileIdPropId) return isNaN(fileIds[slot]) ? null : fileIds[slot]
            const col = columnData[propId]
            if (!col) return undefined
            switch (col.kind) {
                case 'numeric': {
                    const v = col.data[slot]
                    if (isNaN(v)) return null
                    if (_propTypes[propId] === PropertyType.date) return new Date(v)
                    return v
                }
                case 'bool': return col.data[slot] === 255 ? null : col.data[slot] === 1
                case 'string': return col.data[slot]
                case 'tag': return col.sparse[slot]
            }
        }
        function instanceIds() { return instanceIdsArr }
        return { getRawBuffer, readSlot, instanceIds }
    }
    if (STORE === 'pinia') {
        VueLib.markRaw(columnData)
        useColumnStore = PiniaLib.defineStore('columnStore', setup)
    } else {
        const store = setup()
        useColumnStore = () => store
    }
}
const useDataStore = () => DATA

const isTag = (t) => t === PropertyType.tag || t === PropertyType.multi_tags
const objValues = (o) => Object.values(o)

// ── FilterManager (copied from FilterManager.ts) ───────────────────────────

const FilterOperator = {
    equal: 'equal', equalNot: 'equalNot', like: 'like', notLike: 'notLike', lower: 'lower', leq: 'leq',
    greater: 'greater', geq: 'geq', isTrue: 'isTrue', isFalse: 'isFalse', contains: 'contains',
    startsWith: 'startsWith', containsAny: 'containsAny', containsAll: 'containsAll',
    containsNot: 'containsNot', and: 'and', or: 'or', isSet: 'isSet', notSet: 'notSet',
}
const fullTextTypes = new Set([PropertyType.string, PropertyType.path, PropertyType.url])

function isEmpty(value) {
    return value === undefined || value === '' || (Array.isArray(value) && value.length === 0) || value === null
}

const operatorMap = {
    [FilterOperator.geq]:         (a, b) => b == undefined ? true  : a == undefined ? false : a >= b,
    [FilterOperator.leq]:         (a, b) => b == undefined ? true  : a == undefined ? false : a <= b,
    [FilterOperator.lower]:       (a, b) => b == undefined ? true  : a == undefined ? false : a < b,
    [FilterOperator.greater]:     (a, b) => b == undefined ? true  : a == undefined ? false : a > b,
    [FilterOperator.and]:         (a, b) => a && b,
    [FilterOperator.or]:          (a, b) => a || b,
    [FilterOperator.contains]:    (a, b) => isEmpty(b) ? true : isEmpty(a) ? false : a.includes(b),
    [FilterOperator.equal]:       (a, b) => isEmpty(b) ? true : isEmpty(a) ? false : a == b,
    [FilterOperator.equalNot]:    (a, b) => isEmpty(b) ? true : isEmpty(a) ? true  : a != b,
    [FilterOperator.isFalse]:     (a) => isEmpty(a) ? true : a == false,
    [FilterOperator.isTrue]:      (a) => !!a,
    [FilterOperator.isSet]:       (a) => !isEmpty(a),
    [FilterOperator.notSet]:      (a) => isEmpty(a),
    [FilterOperator.startsWith]:  (a, b) => isEmpty(b) ? true : isEmpty(a) ? false : a.startsWith(b),
    [FilterOperator.like]:        (a, b) => isEmpty(b) ? true : isEmpty(a) ? false : !!a.match(b),
    [FilterOperator.notLike]:     (a, b) => isEmpty(b) ? true : isEmpty(a) ? false : !a.match(b),
    [FilterOperator.containsAll]: (a, b) => {
        if (isEmpty(b)) return true
        if (isEmpty(a)) return false
        for (const tag of a)
            for (const tagSet of b)
                if (!tagSet.has(tag)) return false
        return true
    },
    [FilterOperator.containsAny]: (a, b) => {
        if (isEmpty(b)) return true
        if (isEmpty(a)) return false
        for (const tag of a)
            for (const tagSet of b)
                if (tagSet.has(tag)) return true
        return false
    },
    [FilterOperator.containsNot]: (a, b) => {
        if (isEmpty(b)) return true
        if (isEmpty(a)) return true
        for (const tag of a)
            for (const tagSet of b)
                if (tagSet.has(tag)) return false
        return true
    },
}

function applyLeafFilterMaskAnd(filter, slots, mask, properties, tags, tagCache) {
    const col = useColumnStore()
    const property = properties[filter.propertyId]
    const operatorFunc = operatorMap[filter.operator]
    const n = slots.length
    const propId = property.id

    if (property.type !== PropertyType.string) {
        const buf = col.getRawBuffer(propId)
        if (buf instanceof Float64Array) {
            const op = filter.operator
            if (op === FilterOperator.isSet)  { for (let i = 0; i < n; i++) { if (mask[i] && isNaN(buf[slots[i]])) mask[i] = 0 }; return }
            if (op === FilterOperator.notSet) { for (let i = 0; i < n; i++) { if (mask[i] && !isNaN(buf[slots[i]])) mask[i] = 0 }; return }
            if (filter.value == null) return
            const b = property.type === PropertyType.date ? +new Date(filter.value) : Number(filter.value)
            if (isNaN(b)) return
            if (op === FilterOperator.lower)   { for (let i = 0; i < n; i++) { if (mask[i] && (isNaN(buf[slots[i]]) || buf[slots[i]] >= b)) mask[i] = 0 }; return }
            if (op === FilterOperator.leq)     { for (let i = 0; i < n; i++) { if (mask[i] && (isNaN(buf[slots[i]]) || buf[slots[i]] >  b)) mask[i] = 0 }; return }
            if (op === FilterOperator.greater) { for (let i = 0; i < n; i++) { if (mask[i] && (isNaN(buf[slots[i]]) || buf[slots[i]] <= b)) mask[i] = 0 }; return }
            if (op === FilterOperator.geq)     { for (let i = 0; i < n; i++) { if (mask[i] && (isNaN(buf[slots[i]]) || buf[slots[i]] <  b)) mask[i] = 0 }; return }
            if (op === FilterOperator.equal)   { for (let i = 0; i < n; i++) { if (mask[i] && buf[slots[i]] !== b) mask[i] = 0 }; return }
            if (op === FilterOperator.equalNot){ for (let i = 0; i < n; i++) { if (mask[i] && buf[slots[i]] === b) mask[i] = 0 }; return }
        }
    }

    if (property.type === PropertyType.string) {
        const fvLower = filter.value ? filter.value.toLowerCase() : filter.value
        for (let i = 0; i < n; i++) {
            if (!mask[i]) continue
            const raw = col.readSlot(propId, slots[i])
            if (!operatorFunc(raw ? raw.toLowerCase() : raw, fvLower)) mask[i] = 0
        }
        return
    }

    const filterValue = isTag(property.type) && filter.value
        ? (tagCache.get(filter.id) ?? filter.value)
        : filter.value

    for (let i = 0; i < n; i++) {
        if (!mask[i]) continue
        if (!operatorFunc(col.readSlot(propId, slots[i]), filterValue)) mask[i] = 0
    }
}

function applyGroupFilterMask(group, slots, mask, properties, tags, tagCache) {
    if (!group.filters.length) return
    if (group.groupOperator === FilterOperator.and) {
        for (const f of group.filters) {
            if (f.isGroup) applyGroupFilterMask(f, slots, mask, properties, tags, tagCache)
            else applyLeafFilterMaskAnd(f, slots, mask, properties, tags, tagCache)
        }
        return
    }
    const n = slots.length
    const todoMask = new Uint8Array(mask)
    mask.fill(0)
    for (const f of group.filters) {
        let hasTodo = false
        for (let i = 0; i < n; i++) if (todoMask[i]) { hasTodo = true; break }
        if (!hasTodo) break
        const workMask = new Uint8Array(todoMask)
        if (f.isGroup) applyGroupFilterMask(f, slots, workMask, properties, tags, tagCache)
        else applyLeafFilterMaskAnd(f, slots, workMask, properties, tags, tagCache)
        for (let i = 0; i < n; i++) {
            if (workMask[i]) { mask[i] = 1; todoMask[i] = 0 }
        }
    }
}

function extractFromMask(slots, mask) {
    let validCount = 0
    for (let i = 0; i < mask.length; i++) if (mask[i]) validCount++
    const valid = new Int32Array(validCount)
    const reject = new Int32Array(slots.length - validCount)
    let vi = 0, ri = 0
    for (let i = 0; i < slots.length; i++) {
        if (mask[i]) valid[vi++] = slots[i]
        else reject[ri++] = slots[i]
    }
    return { valid, reject }
}

function filterByTextMask(slots, mask, queryText, textProps, tagProps, tags) {
    const col = useColumnStore()
    const query = queryText.toLocaleLowerCase()
    const n = slots.length
    for (let i = 0; i < n; i++) {
        if (!mask[i]) continue
        let found = false
        for (const p of textProps) {
            const val = col.readSlot(p.id, slots[i])
            if (val && val.toLocaleLowerCase().includes(query)) { found = true; break }
        }
        if (!found) {
            outer: for (const p of tagProps) {
                const value = col.readSlot(p.id, slots[i])
                if (!value) continue
                for (const tId of value) {
                    if (tags[tId]?.value.toLocaleLowerCase().includes(query)) { found = true; break outer }
                }
            }
        }
        if (!found) mask[i] = 0
    }
}

function buildTagCache(state, properties, tags) {
    const cache = new Map()
    const visit = (group) => {
        for (const f of group.filters) {
            if (f.isGroup) { visit(f); continue }
            const prop = properties[f.propertyId]
            if (isTag(prop?.type) && Array.isArray(f.value) && f.value.length) {
                cache.set(f.id, f.value.map((v) => new Set([...tags[v].allChildren, v])))
            }
        }
    }
    visit(state.filter)
    return cache
}

// FilterManager.filterSlots without columns download / folders / plugin search.
function filterSlots(state, slots) {
    const { properties, tags } = useDataStore()
    const n = slots.length
    const mask = new Uint8Array(n)
    mask.fill(1)
    const query = state.query
    if (query?.text) {
        const props = objValues(properties)
        const textProps = props.filter(p => fullTextTypes.has(p.type))
        const tagProps = props.filter(p => isTag(p.type))
        filterByTextMask(slots, mask, query.text, textProps, tagProps, tags)
    }
    const tagCache = buildTagCache(state, properties, tags)
    applyGroupFilterMask(state.filter, slots, mask, properties, tags, tagCache)
    return extractFromMask(slots, mask)
}

// ── SortManager (copied from SortManager.ts) ───────────────────────────────

const LAST_STRING = 'zzzzzzzzzzzzzzzzzzzzzzzzzzzz'

const sortParser = {
    [PropertyType.checkbox]:  (x) => (!x ? 0 : 1),
    [PropertyType.color]:     (x) => (isNaN(x) ? -1 : x),
    [PropertyType.date]:      (x) => (!x ? 0 : new Date(x).getTime()),
    [PropertyType.multi_tags]:(x) => (!x ? 0 : x.length),
    [PropertyType.number]:    (x) => (x == undefined ? Number.NEGATIVE_INFINITY : x),
    [PropertyType.path]:      (x) => (!x ? LAST_STRING : x.toLocaleLowerCase()),
    [PropertyType.string]:    (x) => (!x ? LAST_STRING : x.toLocaleLowerCase()),
    [PropertyType.tag]:       (x) => (!x ? LAST_STRING : x.toLocaleLowerCase()),
    [PropertyType.url]:       (x) => (!x ? LAST_STRING : x.toLocaleLowerCase()),
    [PropertyType._ahash]:    (x) => x,
    [PropertyType._sha1]:     (x) => x,
    [PropertyType._folders]:  (x, folders) => folders[x]?.name,
    [PropertyType._height]:   (x) => x,
    [PropertyType._width]:    (x) => x,
    [PropertyType._id]:       (x) => x,
}

function isNumericSortProp(p) {
    switch (p.type) {
        case PropertyType.checkbox: case PropertyType.color: case PropertyType.date:
        case PropertyType.multi_tags: case PropertyType.number: case PropertyType._height:
        case PropertyType._width: case PropertyType._id:
            return true
        default:
            return false
    }
}

function numericSortValue(slot, p, col, folders) {
    const raw = col.readSlot(p.id, slot)
    const parser = sortParser[p.type]
    const v = parser ? parser(raw, folders) : raw
    if (v == null) return Number.NEGATIVE_INFINITY
    const n = +v
    return isNaN(n) ? Number.NEGATIVE_INFINITY : n
}

function stringSortValue(slot, p, col, folders) {
    const raw = col.readSlot(p.id, slot)
    if (p.type === PropertyType.tag) {
        const tagLabel = (Array.isArray(raw) && raw.length > 0) ? p.tags?.[raw[0]]?.value : undefined
        return tagLabel ? tagLabel.toLocaleLowerCase() : LAST_STRING
    }
    const parser = sortParser[p.type]
    const v = parser ? parser(raw, folders) : raw
    return v != null ? String(v) : LAST_STRING
}

function buildSortCols(slots, properties, maxSlot, folders) {
    const col = useColumnStore()
    return properties.map(p => {
        if (isNumericSortProp(p)) {
            const arr = new Float64Array(maxSlot + 1)
            const raw = col.getRawBuffer(p.id)
            if (raw instanceof Float64Array) {
                for (let i = 0; i < slots.length; i++) {
                    const v = raw[slots[i]]
                    arr[slots[i]] = isNaN(v) ? Number.NEGATIVE_INFINITY : v
                }
                return arr
            }
            for (let i = 0; i < slots.length; i++) arr[slots[i]] = numericSortValue(slots[i], p, col, folders)
            return arr
        }
        const arr = new Array(maxSlot + 1).fill(LAST_STRING)
        for (let i = 0; i < slots.length; i++) arr[slots[i]] = stringSortValue(slots[i], p, col, folders)
        return arr
    })
}

function compareSlotsByCols(slotA, slotB, cols, orders) {
    for (let k = 0; k < cols.length; k++) {
        const va = cols[k][slotA], vb = cols[k][slotB]
        if (va < vb) return -orders[k]
        if (va > vb) return orders[k]
    }
    return slotA - slotB
}

function sortByPackedKey(slots, sortCols, orders) {
    const n = slots.length
    if (n === 0) return slots
    const colRanks = [], numUniques = []
    let keyScale = 1
    for (let k = 0; k < sortCols.length; k++) {
        const col = sortCols[k]
        const ascending = orders[k] === 1
        let vals, unique
        if (col instanceof Float64Array) {
            const v = new Float64Array(n)
            for (let i = 0; i < n; i++) v[i] = col[slots[i]]
            vals = v
            unique = Float64Array.from(new Set(v))
            unique.sort()
        } else {
            const v = new Array(n)
            for (let i = 0; i < n; i++) v[i] = col[slots[i]]
            vals = v
            unique = Array.from(new Set(v)).sort()
        }
        const numUnique = unique.length
        if (keyScale > Number.MAX_SAFE_INTEGER / numUnique / (n + 1)) return null
        keyScale *= numUnique
        const rankMap = new Map()
        for (let j = 0; j < numUnique; j++) rankMap.set(unique[j], ascending ? j : numUnique - 1 - j)
        const ranks = new Uint32Array(n)
        for (let i = 0; i < n; i++) ranks[i] = rankMap.get(vals[i]) ?? 0
        colRanks.push(ranks)
        numUniques.push(numUnique)
    }
    const packed = new Float64Array(n)
    let multiplier = 1
    for (let k = colRanks.length - 1; k >= 0; k--) {
        const ranks = colRanks[k]
        for (let i = 0; i < n; i++) packed[i] += ranks[i] * multiplier
        multiplier *= numUniques[k]
    }
    for (let i = 0; i < n; i++) packed[i] = packed[i] * n + i
    packed.sort()
    const result = new Int32Array(n)
    for (let i = 0; i < n; i++) result[i] = slots[packed[i] % n]
    return result
}

// SortManager.sort without column download / scores.
function sortSlots(sortBy, slots) {
    const data = useDataStore()
    const properties = sortBy.map(s => data.properties[s.id])
    const ords = sortBy.map(s => s.dir)
    let maxSlot = 0
    for (let i = 0; i < slots.length; i++) if (slots[i] > maxSlot) maxSlot = slots[i]
    const cols = buildSortCols(slots, properties, maxSlot, data.folders)
    if (cols.length === 0) return slots.slice()
    return sortByPackedKey(slots, cols, ords) ?? (() => {
        const s = slots.slice()
        if (cols.length === 1) {
            const col0 = cols[0], ord0 = ords[0]
            s.sort((a, b) => { const d = col0[a] < col0[b] ? -ord0 : col0[a] > col0[b] ? ord0 : 0; return d || a - b })
        } else {
            s.sort((a, b) => compareSlotsByCols(a, b, cols, ords))
        }
        return s
    })()
}

// ── GroupManager (copied from GroupManager.ts + group/*) ───────────────────

const DateUnit = { Year: 'Year', Month: 'Month', Week: 'Week', Day: 'Day', Hour: 'Hour', Minute: 'Minute', Second: 'Second' }
const DateUnitFactor = { Second: 1, Minute: 60, Hour: 3600, Day: 86400, Week: 604800 }
const GroupType = { All: 'all', Property: 'property', Cluster: 'cluster' }

function isNoValue(x) {
    return x == undefined || x === '' || (typeof x === 'number' && Number.isNaN(x))
}
const valueParser = {
    [PropertyType.checkbox]: (x) => { if (!x) return false; return true },
    [PropertyType.date]:     (x) => { if (!x) return undefined; return x },
    [PropertyType.number]:   (x) => { if (isNoValue(x)) return undefined; return x },
    [PropertyType.string]:   (x) => { if (!x) return undefined; return x },
    [PropertyType.tag]:      (x) => { if (Array.isArray(x)) return x; return undefined },
    [PropertyType.multi_tags]:(x) => { if (Array.isArray(x)) return x; return undefined },
}

function dateBucketKey(date, stepSize, unit) {
    if (!date) return undefined
    if (!stepSize) stepSize = 1
    if (!unit) unit = DateUnit.Day
    if (unit === DateUnit.Year) return Math.floor(date.getUTCFullYear() / stepSize)
    if (unit === DateUnit.Month) {
        const totalMonths = date.getUTCFullYear() * 12 + date.getUTCMonth()
        return Math.floor(totalMonths / stepSize)
    }
    const stepMs = stepSize * DateUnitFactor[unit] * 1000
    return Math.floor(date.getTime() / stepMs)
}

function dateBucketRange(key, stepSize, unit) {
    if (!stepSize) stepSize = 1
    if (unit === DateUnit.Year) {
        const year = key * stepSize
        return { first: new Date(Date.UTC(year, 0, 1)), last: new Date(Date.UTC(year + stepSize, 0, 1)) }
    }
    if (unit === DateUnit.Month) {
        const startMonth = key * stepSize, endMonth = startMonth + stepSize
        return {
            first: new Date(Date.UTC(Math.floor(startMonth / 12), startMonth % 12, 1)),
            last:  new Date(Date.UTC(Math.floor(endMonth / 12), endMonth % 12, 1)),
        }
    }
    const stepMs = stepSize * DateUnitFactor[unit] * 1000
    return { first: new Date(key * stepMs), last: new Date(key * stepMs + stepMs - 1) }
}

class GroupValueIndex {
    constructor() { this.index = new Map(); this.idCounter = 1 }
    get(valueKey) {
        let idx = this.index
        for (const value of valueKey) {
            if (!idx.has(value)) idx.set(value, new Map())
            idx = idx.get(value)
        }
        if (!idx.has(null)) idx.set(null, this.idCounter++)
        return idx.get(null)
    }
}

function buildGroup(id, slots, type = GroupType.All) {
    return {
        id, key: [], slots, type, children: [], depth: 0, order: -1, start: 0, end: 0,
        meta: { propertyValues: [] }, view: { closed: false },
    }
}

function refreshSubGroupType(parent) {
    if (!parent.children.length) { parent.subGroupType = undefined; return }
    const t = parent.children[0].type
    parent.subGroupType = parent.children.every(c => c.type === t) ? t : undefined
}

function sortGroupByProperty(group, direction, properties, folders) {
    const sortable = {}
    for (const child of group.children) {
        const values = []
        for (const propValue of child.meta.propertyValues) {
            const prop = properties[propValue.propertyId]
            const type = isTag(prop.type) ? PropertyType.tag : prop.type
            let value = propValue.value
            if (isTag(type) && value != undefined) {
                const tagObj = prop.tags?.[value]
                value = tagObj ? tagObj.value : String(value)
            }
            value = sortParser[type](value, folders)
            values.push(value)
        }
        sortable[child.id] = values
    }
    group.children.sort((ca, cb) => {
        const a = sortable[ca.id], b = sortable[cb.id]
        for (let i = 0; i < a.length; i++) {
            if (a[i] == b[i]) continue
            if (a[i] < b[i]) return -1 * direction
            return 1 * direction
        }
        return 0
    })
}

function sortGroup(group, option) {
    const data = useDataStore()
    if (group.children.length == 0) return
    sortGroupByProperty(group, option.direction, data.properties, data.folders)
    for (let i = 0; i < group.children.length; i++) group.children[i].parentIdx = i
}

function setOrder(group) {
    let i = 0
    const recursive = (g) => { g.order = i++; g.children.forEach(c => recursive(c)) }
    recursive(group)
}

class GroupManager {
    constructor(state) {
        this.state = state
        this.result = { root: undefined, index: {}, imageToGroups: new Map(), valueIndex: new GroupValueIndex() }
        this._leafGroups = []
        this._rebuildingTree = false
    }

    group(slots) {
        const data = useDataStore()
        let maxSlot = 0
        for (let i = 0; i < slots.length; i++) if (slots[i] > maxSlot) maxSlot = slots[i]
        this._posArr = new Int32Array(maxSlot + 1).fill(-1)
        for (let i = 0; i < slots.length; i++) this._posArr[slots[i]] = i

        const lastIndex = this.result.index ?? {}
        this.result.root = buildGroup(0, Array.from(slots))
        this.result.index = {}
        this.result.imageToGroups = new Map()
        this._leafGroups = []
        this.regsiterGroup(this.result.root)

        this._rebuildingTree = true
        if (this.state.groupBy.length > 0) {
            this.computePropertySubGroup(this.result.root, this.state.groupBy, data.properties, data.tags)
        }
        this._rebuildingTree = false

        const ids = useColumnStore().instanceIds()
        const leafGroups = this.state.groupBy.length > 0 ? this._leafGroups : [this.result.root]
        for (const g of leafGroups) {
            for (const s of g.slots) {
                const id = ids[s]
                let set = this.result.imageToGroups.get(id)
                if (!set) { set = new Set(); this.result.imageToGroups.set(id, set) }
                set.add(g.id)
            }
        }
        for (const id of Object.keys(this.result.index)) {
            const group = this.result.index[id]
            if (lastIndex[id]) group.view = lastIndex[id].view
        }
        setOrder(this.result.root)
        return this.result
    }

    saveImagesToGroup(group) {
        if (this._rebuildingTree) return
        const ids = useColumnStore().instanceIds()
        for (const s of group.slots) {
            const id = ids[s]
            let set = this.result.imageToGroups.get(id)
            if (!set) { set = new Set(); this.result.imageToGroups.set(id, set) }
            set.add(group.id)
        }
    }

    removeChildren(group) {
        const detach = (c) => {
            c.children.forEach(detach)
            delete this.result.index[c.id]
        }
        group.children.forEach(detach)
        group.children.length = 0
        group.subGroupType = undefined
    }

    setChildGroup(parent, groups) {
        this.removeChildren(parent)
        for (const group of groups) {
            group.parentIdx = parent.children.length
            group.parent = parent
            group.depth = parent.depth + 1
            parent.children.push(group)
            this.regsiterGroup(group)
            this.saveImagesToGroup(group)
        }
        refreshSubGroupType(parent)
    }

    regsiterGroup(group) { this.result.index[group.id] = group }

    computePropertySubGroup(group, groupBy, properties, tags) {
        const col = useColumnStore()
        const property = properties[groupBy[0]]
        const option = this.state.options[property.id]
        const isDateType = property.type === PropertyType.date
        const isTagType = isTag(property.type)
        const rawBuf = col.getRawBuffer(property.id)
        const parser = !isDateType && !isTagType ? valueParser[property.type] : null

        const tagWithParents = {}
        if (isTagType && property.tags) {
            for (const tag of objValues(property.tags)) {
                tagWithParents[tag.id] = new Set(tag.allParents)
                tagWithParents[tag.id].add(tag.id)
            }
        }
        group.subGroupType = GroupType.Property

        const buckets = new Map()
        const bucketMeta = new Map()
        for (const s of group.slots) {
            if (isDateType) {
                const raw = rawBuf?.[s]
                const bk = raw ? dateBucketKey(raw instanceof Date ? raw : new Date(raw), option.stepSize, option.stepUnit) : undefined
                if (bk !== undefined && !bucketMeta.has(bk)) {
                    const range = dateBucketRange(bk, option.stepSize, option.stepUnit)
                    bucketMeta.set(bk, { displayVal: range.first, intervalEnd: range.last })
                }
                let arr = buckets.get(bk); if (!arr) { arr = []; buckets.set(bk, arr) }; arr.push(s)
            } else if (isTagType) {
                const tagIds = rawBuf?.[s]
                if (!Array.isArray(tagIds) || !tagIds.length) {
                    let arr = buckets.get(undefined); if (!arr) { arr = []; buckets.set(undefined, arr) }; arr.push(s)
                    continue
                }
                let placed = false
                for (const v of tagIds) {
                    if (!v) continue
                    const parents = tagWithParents[v]
                    if (!parents) continue
                    for (const p of parents) {
                        let arr = buckets.get(p); if (!arr) { arr = []; buckets.set(p, arr) }
                        if (arr.length === 0 || arr[arr.length - 1] !== s) arr.push(s)
                        placed = true
                    }
                }
                if (!placed) {
                    let arr = buckets.get(undefined); if (!arr) { arr = []; buckets.set(undefined, arr) }; arr.push(s)
                }
            } else {
                let raw = rawBuf?.[s]
                if (property.type === PropertyType.checkbox && raw === 255) raw = null
                const kv = parser(raw)
                let arr = buckets.get(kv); if (!arr) { arr = []; buckets.set(kv, arr) }; arr.push(s)
            }
        }

        const subGroups = []
        for (const [kv, slots] of buckets) {
            const key = group.key.concat([kv])
            const groupId = this.result.valueIndex.get(key)
            if (!this.result.index[groupId]) {
                const meta = bucketMeta.get(kv)
                const displayVal = meta !== undefined ? meta.displayVal : kv
                const intervalEnd = meta?.intervalEnd
                const newGroup = buildGroup(groupId, [], GroupType.Property)
                newGroup.meta.propertyValues = [{ propertyId: property.id, value: displayVal, valueEnd: intervalEnd, unit: option.stepUnit }]
                newGroup.key = key
                this.regsiterGroup(newGroup)
                subGroups.push(newGroup)
            }
            const target = this.result.index[groupId]
            for (const s of slots) target.slots.push(s)
        }

        this.setChildGroup(group, subGroups)
        if (groupBy.length > 1) {
            for (const c of subGroups) this.computePropertySubGroup(c, groupBy.slice(1), properties, tags)
        } else {
            for (const g of subGroups) this._leafGroups.push(g)
        }
        sortGroup(group, option)
    }
}

// ── checksums (same as rust/src/main.rs) ───────────────────────────────────

const mix = (h, v) => (Math.imul(h, 31) + v) | 0

function hashSlots(slots) {
    let h = 0
    for (let i = 0; i < slots.length; i++) h = mix(h, slots[i] + 1)
    return { count: slots.length, hash: h >>> 0 }
}

function hashTree(root) {
    let h = 0, groups = 0, entries = 0
    const visit = (g) => {
        h = mix(h, 0x9e3779b9 ^ g.children.length)
        if (g.children.length === 0) {
            entries += g.slots.length
            for (const s of g.slots) h = mix(h, s + 1)
        } else {
            for (const c of g.children) { groups++; visit(c) }
        }
    }
    visit(root)
    return { count: groups, entries, hash: h >>> 0 }
}

// ── ops ────────────────────────────────────────────────────────────────────

let _fid = 0
const leaf = (propertyId, operator, value) => ({ id: ++_fid, propertyId, operator, value })
const and = (...filters) => ({ id: ++_fid, isGroup: true, groupOperator: FilterOperator.and, depth: 0, filters })
const or = (...filters) => ({ id: ++_fid, isGroup: true, groupOperator: FilterOperator.or, depth: 1, filters })
const fstate = (filter, text = '') => ({ folders: [], filter, query: { type: 'text', text } })

function buildOps(D) {
    const w = D.words
    const filterOp = (state) => (slots) => filterSlots(state, slots).valid
    const sortOp = (sortBy) => (slots) => sortSlots(sortBy, slots)
    const groupOp = (groupBy, options) => {
        const gm = new GroupManager({ groupBy, options, sha1Mode: false })
        return (slots) => gm.group(slots).root
    }
    const asc = (id) => ({ id, dir: 1 }), desc = (id) => ({ id, dir: -1 })
    const opt = (stepUnit) => ({ direction: 1, type: 'property', stepUnit, stepSize: 1 })
    const compound = and(
        leaf(P.number, FilterOperator.greater, 2000),
        leaf(P.date, FilterOperator.greater, '2018-01-01'),
        or(leaf(P.tags, FilterOperator.containsAny, [5]), leaf(P.text, FilterOperator.contains, 'ka')),
    )
    return [
        ['filter', 'number > 5000',          filterOp(fstate(and(leaf(P.number, FilterOperator.greater, 5000))))],
        ['filter', 'number isSet',           filterOp(fstate(and(leaf(P.number, FilterOperator.isSet, undefined))))],
        ['filter', 'score <= 250.5',         filterOp(fstate(and(leaf(P.score, FilterOperator.leq, 250.5))))],
        ['filter', 'date > 2020-01-01',      filterOp(fstate(and(leaf(P.date, FilterOperator.greater, '2020-01-01'))))],
        ['filter', 'checkbox isTrue',        filterOp(fstate(and(leaf(P.check, FilterOperator.isTrue, undefined))))],
        ['filter', 'text contains',          filterOp(fstate(and(leaf(P.text, FilterOperator.contains, 'lumi'))))],
        ['filter', 'text startsWith',        filterOp(fstate(and(leaf(P.text, FilterOperator.startsWith, 'ka'))))],
        ['filter', 'text like (regex)',      filterOp(fstate(and(leaf(P.text, FilterOperator.like, '^ka.*_\\d{3}\\.jpg$'))))],
        ['filter', 'label equal',            filterOp(fstate(and(leaf(P.label, FilterOperator.equal, w[7]))))],
        ['filter', 'tags containsAny',       filterOp(fstate(and(leaf(P.tags, FilterOperator.containsAny, [3, 17]))))],
        ['filter', 'tags containsNot',       filterOp(fstate(and(leaf(P.tags, FilterOperator.containsNot, [1]))))],
        ['filter', 'search box (text+tags)', filterOp(fstate(and(), 'lumi'))],
        ['filter', 'compound and/or',        filterOp(fstate(compound))],
        ['sort', 'number',                   sortOp([asc(P.number)])],
        ['sort', 'score (float) desc',       sortOp([desc(P.score)])],
        ['sort', 'date',                     sortOp([asc(P.date)])],
        ['sort', 'text',                     sortOp([asc(P.text)])],
        ['sort', 'tags (count)',             sortOp([asc(P.tags)])],
        ['sort', 'label, score desc',        sortOp([asc(P.label), desc(P.score)])],
        ['group', 'number (10k values)',     groupOp([P.number], { [P.number]: opt() })],
        ['group', 'date by month',           groupOp([P.date], { [P.date]: opt(DateUnit.Month) })],
        ['group', 'label (300 values)',      groupOp([P.label], { [P.label]: opt() })],
        ['group', 'checkbox',                groupOp([P.check], { [P.check]: opt() })],
        ['group', 'tags (+parents)',         groupOp([P.tags], { [P.tags]: opt() })],
        ['group', 'label > date by year',    groupOp([P.label, P.date], { [P.label]: opt(), [P.date]: opt(DateUnit.Year) })],
        ['group', 'text (~N values)',        groupOp([P.text], { [P.text]: opt() })],
        ['pipeline', 'compound > sort > tags', (() => {
            const st = fstate(compound), sb = [asc(P.label), desc(P.score)]
            const gm = new GroupManager({ groupBy: [P.tags], options: { [P.tags]: opt() }, sha1Mode: false })
            return (slots) => gm.group(sortSlots(sb, filterSlots(st, slots).valid)).root
        })()],
    ]
}

// ── runner ─────────────────────────────────────────────────────────────────

function median(xs) { const s = xs.slice().sort((a, b) => a - b); return s[s.length >> 1] }

function main() {
    const live0 = MEM ? liveBytes() : 0
    DATA = generate(N)
    setupColumnStore(DATA)
    const impl = ENGINE + (STORE === 'pinia' ? '' : '-raw')
    out(JSON.stringify({ impl, meta: true, n: N, gen_ms: Math.round(DATA.genMs), ...(MEM ? { live_bytes: liveBytes() - live0 } : {}) }))
    // --wait (set by memwatch): block until stdin says go, so the load is left out of the peak.
    if (ARGV.includes('--wait')) {
        if (IS_NODE) require('fs').readSync(0, Buffer.alloc(16))
        else readline()
    }
    const all = new Int32Array(N)
    for (let i = 0; i < N; i++) all[i] = i
    for (const [kind, name, fn] of buildOps(DATA)) {
        const id = kind + ': ' + name
        if (ONLY && !ONLY.test(id)) continue
        if (SKIP && SKIP.test(id)) continue
        if (OP && id !== OP) continue
        if (MEM) {
            const base = liveBytes()
            const t0 = now()
            let result = fn(all)
            const ms = now() - t0
            const retained = liveBytes() - base
            const res = ArrayBuffer.isView(result) ? hashSlots(result) : hashTree(result)
            result = null
            out(JSON.stringify({ impl, n: N, kind, op: name, mem: true, ms: +ms.toFixed(3), retained_bytes: retained, ...res }))
            continue
        }
        const times = []
        let res
        for (let r = 0; r < WARMUP + REPS; r++) {
            doGC()
            const t0 = now()
            const result = fn(all)
            const dt = now() - t0
            if (r >= WARMUP) times.push(dt)
            res = ArrayBuffer.isView(result) ? hashSlots(result) : hashTree(result)
        }
        out(JSON.stringify({ impl, n: N, kind, op: name, ms: +median(times).toFixed(3), min_ms: +Math.min(...times).toFixed(3), ...res }))
    }
}

// lines.js loads this file as a library (data + GroupManager) and runs its own ops.
if (!globalThis.BENCH_LIB) main()
