'use strict'
/*
 * Lines benchmark — JS side: what the scrollers spend laying out lines, with the REAL front code.
 *
 * `dist/front-lines.js` (built by build-front-lines.js) is panoptic_front's scrollLayout.ts,
 * treeLines.ts, gridLines.ts and sha1Piles.ts, type-stripped and unchanged. The trees are built by
 * bench.js's copy of GroupManager (loaded as a library), outside the timings.
 *
 * Views:
 *  - grid  = TreeScroller: TreeGeometry (images per line from the width, image size and depth) +
 *            treeSource; a header line per group, image (or pile) lines in open leaves;
 *  - table = GridScroller: gridSource; a header line per leaf, one row per image (or pile), the
 *            row estimate `rowSize` (imageSize + 4 with images, 28 without).
 * Ops (on ScrollLayout, as TreeScroller / GridScroller / VirtualScroller call it):
 *  - build: layout.rebuild() (a new result);
 *  - resize: geometry.setParams(new width / image size) + layout.refresh();
 *  - toggle one: close + open a group with refreshNode; close all / open all: flip every
 *    `view.closed` + layout.refresh();
 *  - locate / offsetOf: pixel -> line and line -> pixel (per call);
 *  - window: VirtualScroller.update's walk over viewport + overscan, making the line objects
 *    (leafLine / group line, gridRow / gridGroupLine) for the lines in it;
 *  - all lines: every line object of the whole list (the eager way), for comparison;
 *  - measure screen (table): setMeasured on the rows of one screen of a fresh layout.
 *
 *   node --max-old-space-size=14000 lines.js --n=1000000 --store=raw
 *   jsc lines.js -- --n=1000000 --store=raw
 */
;(function () {
    const IS_NODE_ = typeof process !== 'undefined' && !!(process.versions && process.versions.node)
    const HERE = IS_NODE_ ? __dirname : '.'
    const loadScript = IS_NODE_ ? (f) => require('vm').runInThisContext(require('fs').readFileSync(f, 'utf8'), { filename: f }) : load
    globalThis.BENCH_LIB = true
    loadScript(HERE + '/bench.js')            // ARGV, arg, N, REPS, WARMUP, out, now, generate, GroupManager, mix, median...
    loadScript(HERE + '/dist/front-lines.js') // FrontLines
    if (STORE !== 'raw') throw new Error('run with --store=raw (the layout reads groups, not the column store)')
    const { scrollLayout: SL, treeLines: TL, gridLines: GL, sha1Piles: SP } = FrontLines

    const TREES = arg('trees', 'flat,label-year,tags,text,label-year-piles').split(',')
    const VIEWS = arg('views', 'grid,table').split(',')
    const VH = 1000, OVERSCAN = 300          // viewport px, VirtualScroller's overscan (both scrollers pass 300)
    const WIDTH_OFFSET = 17                  // TreeScroller: scrollbar + 2px
    const WIDTHS = [800, 1440, 2560], IMAGES = [100, 200], DEF_W = 1440, DEF_I = 200
    const ROWS = [104, 28], DEF_ROW = 104    // GridScroller rowSize: imageSize 100 + 4, or 28 without images
    const PROPS = 2, PILE_PROPS = 1          // properties drawn under a card / under a pile card
    const impl = ENGINE

    DATA = generate(N)
    setupColumnStore(DATA)
    const ids = DATA.ids
    // Synthetic sha1s with ~30% duplicates (same formula as rust/src/lines.rs).
    const M = Math.max(1, Math.floor(N * 0.7))
    const sha1s = new Array(N)
    for (let s = 0; s < N; s++) sha1s[s] = 'h' + ((Math.imul(s, 2654435761) >>> 0) % M)

    const opt = (stepUnit) => ({ direction: 1, type: 'property', stepUnit, stepSize: 1 })
    const DEFS = {
        'flat':             { groupBy: [], options: {} },
        'label-year':       { groupBy: [P.label, P.date], options: { [P.label]: opt(), [P.date]: opt(DateUnit.Year) } },
        'tags':             { groupBy: [P.tags], options: { [P.tags]: opt() } },
        'text':             { groupBy: [P.text], options: { [P.text]: opt() } },
        'label-year-piles': { groupBy: [P.label, P.date], options: { [P.label]: opt(), [P.date]: opt(DateUnit.Year) }, piles: true },
    }

    function buildHost(def) {
        const gm = new GroupManager({ groupBy: def.groupBy, options: def.options, sha1Mode: !!def.piles })
        const all = new Int32Array(N)
        for (let i = 0; i < N; i++) all[i] = i
        const res = gm.group(all)
        const pileIndex = new Map()
        let groups = 0, leaves = 0
        const stack = [res.root]
        while (stack.length) {
            const g = stack.pop()
            if (g !== res.root) groups++
            if (g.children.length) { for (const c of g.children) stack.push(c); continue }
            leaves++
            if (def.piles) { const p = SP.computeSha1Piles(g.slots, sha1s); if (p) pileIndex.set(g.id, p) }
        }
        return { root: res.root, index: res.index, pileIndex, rev: 0, groups, leaves }
    }

    const gridParams = (w, img) => ({ contentWidth: Math.max(0, w - WIDTH_OFFSET), imageSize: img, propertyCount: PROPS, pilePropertyCount: PILE_PROPS })

    function makeView(view, host) {
        if (view === 'grid') {
            const geometry = new TL.TreeGeometry(gridParams(DEF_W, DEF_I))
            const source = TL.treeSource(() => host, geometry, () => false)
            return { view, host, geometry, source, layout: new SL.ScrollLayout(source) }
        }
        const v = { view, host, row: DEF_ROW }
        v.source = GL.gridSource(() => host, () => v.row)
        v.layout = new SL.ScrollLayout(v.source)
        return v
    }

    // The line object the scroller hands to its line component (TreeScroller.groupItem is a literal in
    // the .vue, copied here; the rest is front code).
    function makeItem(v, ref) {
        const host = v.host
        if (v.view === 'grid') {
            if (ref.index < 0) {
                const group = host.index[ref.node]
                return { id: group.id, type: 'group', data: group, depth: group.depth, size: TL.GROUP_LINE_SIZE, nbClusters: 10 }
            }
            return TL.leafLine(host, ref.node, ref.index, v.geometry)
        }
        if (ref.index < 0) return GL.gridGroupLine(host.index[ref.node])
        return GL.gridRow(host, ids, ref)
    }

    // Structural hash of a line (no group ids: the JS and Rust trees number groups differently).
    function hashItem(h, v, ref, item) {
        if (ref.index < 0) {
            const g = v.host.index[ref.node]
            return mix(mix(mix(h, 1), g.depth), v.view === 'grid' ? TL.GROUP_LINE_SIZE : GL.GRID_GROUP_LINE_SIZE)
        }
        if (v.view === 'grid') return mix(mix(mix(mix(mix(h, 2), item.depth), item.start), item.count), item.size)
        if (item.type === 'pile') return mix(mix(mix(h, 4), ids[item.data.slots[0]]), item.data.slots.length)
        return mix(mix(h, 3), item.data.id)
    }

    // Every line in display order, straight from the LayoutSource (what ScrollLayout shows).
    function walkLines(v, visit) {
        const src = v.source
        const stack = [src.root()]
        while (stack.length) {
            const id = stack.pop()
            if (src.headerSize(id) > 0) visit({ node: id, index: -1 })
            if (!src.isOpen(id)) continue
            const k = src.childCount(id)
            if (k) { for (let i = k - 1; i >= 0; i--) stack.push(src.child(id, i)); continue }
            const L = src.bodyLines(id)
            for (let i = 0; i < L; i++) visit({ node: id, index: i })
        }
    }

    function allLinesCheck(v) {
        let h = 0, lines = 0, height = 0
        walkLines(v, ref => {
            const item = makeItem(v, ref)
            h = hashItem(h, v, ref, item)
            lines++
            height += ref.index < 0 ? Math.round(v.source.headerSize(ref.node)) : Math.max(1, Math.round(v.source.lineEstimate(ref.node)))
        })
        return { lines, height, hash: h >>> 0 }
    }

    function windowAt(v, y) {
        const L = v.layout
        const from = Math.max(0, y - OVERSCAN), to = y + VH + OVERSCAN
        const items = []
        let line = L.locate(from)
        while (line && line.top < to) {
            items.push(line, makeItem(v, line))
            const end = line.top + L.sizeOf(line)
            const next = end < L.height ? L.locate(end) : null
            line = next && next.top > line.top ? next : null
        }
        return items
    }

    function timeIt(reps, f) {
        for (let w = 0; w < WARMUP; w++) f()
        const t = []
        for (let r = 0; r < reps; r++) { const t0 = now(); f(); t.push(now() - t0) }
        return { ms: +median(t).toFixed(4), min_ms: +Math.min(...t).toFixed(4) }
    }
    const emit = (v, tree, cfg, op, res) => out(JSON.stringify({ impl, n: N, view: v.view, tree, cfg, op, ...res }))
    const cfgName = (v) => v.view === 'grid' ? `w${DEF_W} i${DEF_I}` : `row${v.row}`

    function setOpenAll(host, open) {
        for (const id in host.index) if (+id !== host.root.id) host.index[id].view.closed = !open
    }

    function run(tree, v) {
        const L = v.layout
        const host = v.host
        L.rebuild()
        const base = cfgName(v)
        emit(v, tree, base, 'build', { ...timeIt(REPS, () => L.rebuild()), nodes: L.nodeCount, groups: host.groups, leaves: host.leaves, height: L.height })

        // resize / row size change, then the eager all-lines cost + the agreement check per config
        const configs = v.view === 'grid'
            ? WIDTHS.flatMap(w => IMAGES.map(i => [w, i]))
            : ROWS.map(r => [r])
        for (const c of configs) {
            const name = v.view === 'grid' ? `w${c[0]} i${c[1]}` : `row${c[0]}`
            const apply = (cc) => {
                if (v.view === 'grid') v.geometry.setParams(gridParams(cc[0], cc[1]))
                else v.row = cc[0]
                L.refresh()
            }
            const def = v.view === 'grid' ? [DEF_W, DEF_I] : [DEF_ROW]
            // time going from another config to this one (from the default, or to the default from 800/100)
            const other = name === base ? (v.view === 'grid' ? [800, 100] : [28]) : def
            const t = []
            for (let r = 0; r < WARMUP + REPS; r++) {
                apply(other)
                const t0 = now(); apply(c); const dt = now() - t0
                if (r >= WARMUP) t.push(dt)
            }
            emit(v, tree, name, v.view === 'grid' ? 'resize' : 'row size', { ms: +median(t).toFixed(4), min_ms: +Math.min(...t).toFixed(4), height: L.height })
            const check = allLinesCheck(v)
            const tAll = timeIt(Math.min(REPS, 3), () => { const lines = []; walkLines(v, ref => lines.push(makeItem(v, ref))); return lines })
            emit(v, tree, name, 'all lines', { ...tAll, ...check, layout_height: L.height })
        }
        if (v.view === 'grid') v.geometry.setParams(gridParams(DEF_W, DEF_I))
        else v.row = DEF_ROW
        L.refresh()

        // open / close
        const kids = host.root.children
        if (kids.length) {
            const g = kids[kids.length >> 1]
            // 100 close + open pairs per sample (one is below the jsc timer's resolution), per pair
            const tt = timeIt(REPS * 4, () => {
                for (let k = 0; k < 100; k++) {
                    g.view.closed = true; L.refreshNode(g.id)
                    g.view.closed = false; L.refreshNode(g.id)
                }
            })
            emit(v, tree, base, 'toggle one', { ms: +(tt.ms / 100).toFixed(6), min_ms: +(tt.min_ms / 100).toFixed(6), per: 'close+open' })
            const tc = [], to = []
            for (let r = 0; r < WARMUP + REPS; r++) {
                let t0 = now(); setOpenAll(host, false); L.refresh(); const c = now() - t0
                const hClosed = L.height
                t0 = now(); setOpenAll(host, true); L.refresh(); const o = now() - t0
                if (r >= WARMUP) { tc.push(c); to.push(o) }
                if (r === 0) v.closedHeight = hClosed
            }
            emit(v, tree, base, 'close all', { ms: +median(tc).toFixed(4), min_ms: +Math.min(...tc).toFixed(4), height: v.closedHeight })
            emit(v, tree, base, 'open all', { ms: +median(to).toFixed(4), min_ms: +Math.min(...to).toFixed(4), height: L.height })
        }

        // locate / offsetOf: per call, over the same random pixels as the Rust side
        const Q = 10000
        const rnd = mulberry32(42)
        const ys = new Float64Array(Q)
        for (let i = 0; i < Q; i++) ys[i] = Math.floor(rnd() * L.height)
        let refs = new Array(Q), hLoc = 0, hOff = 0
        const tl = timeIt(REPS, () => { for (let i = 0; i < Q; i++) refs[i] = L.locate(ys[i]) })
        for (let i = 0; i < Q; i++) hLoc = mix(mix(hLoc, refs[i].top), refs[i].index)
        const offs = new Float64Array(Q)
        const toff = timeIt(REPS, () => { for (let i = 0; i < Q; i++) offs[i] = L.offsetOf(refs[i]) })
        for (let i = 0; i < Q; i++) hOff = mix(hOff, offs[i])
        emit(v, tree, base, 'locate', { ms: +(tl.ms / Q).toFixed(6), min_ms: +(tl.min_ms / Q).toFixed(6), per: 'call', hash: hLoc >>> 0 })
        emit(v, tree, base, 'offsetOf', { ms: +(toff.ms / Q).toFixed(6), min_ms: +(toff.min_ms / Q).toFixed(6), per: 'call', hash: hOff >>> 0 })

        // window: one VirtualScroller.update walk at 200 random positions
        const W = 200, wt = []
        let hWin = 0, nWin = 0
        for (let i = 0; i < W + 20; i++) {
            const y = ys[i % Q]
            const t0 = now(); const items = windowAt(v, y); const dt = now() - t0
            if (i >= 20) {
                wt.push(dt)
                for (let k = 0; k < items.length; k += 2) { hWin = hashItem(mix(hWin, items[k].top), v, items[k], items[k + 1]); nWin++ }
            }
        }
        emit(v, tree, base, 'window', { ms: +median(wt).toFixed(4), min_ms: +Math.min(...wt).toFixed(4), lines: Math.round(nWin / W), hash: hWin >>> 0 })

        // table: the rows of one screen measured on a fresh layout (first measure of a leaf = O(its rows))
        if (v.view === 'table') {
            const y = ys[0]
            const screen = windowAt(v, y).filter((x, k) => k % 2 === 0 && x.index >= 0)
            const tm = []
            for (let r = 0; r < WARMUP + REPS; r++) {
                L.clearMeasured()
                const t0 = now()
                for (const ref of screen) L.setMeasured(ref, v.row + 7)
                const dt = now() - t0
                if (r >= WARMUP) tm.push(dt)
            }
            emit(v, tree, base, 'measure screen', { ms: +median(tm).toFixed(4), min_ms: +Math.min(...tm).toFixed(4), rows: screen.length, height: L.height })
            L.clearMeasured()
        }
    }

    for (const tree of TREES) {
        const host = buildHost(DEFS[tree])
        for (const view of VIEWS) run(tree, makeView(view, host))
    }
})()
