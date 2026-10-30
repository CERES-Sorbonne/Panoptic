# Collection benchmark: TS vs Rust filter / sort / group

Compares the hot paths of `FilterManager`, `SortManager` and `GroupManager`
(`panoptic_front/src/core`) with a Rust implementation of the same semantics, on 1M–10M
synthetic images.

- `js/bench.js`: a stripped-down copy of the TS code, covering the leaf filters, OR/AND
  masks, the search box, `buildSortCols` + `sortByPackedKey`, `computePropertySubGroup`
  + `sortGroup` + the `imageToGroups` sweep. Column layout is the same as `columnStore`. With
  `--store=pinia` (the default), the column store is a real Pinia setup store, so every
  `col.readSlot()` goes through the same reactive proxy and action wrapper as in the app.
  `--store=raw` uses a plain object instead.
- `rust/`: the same ops on Rust columns: `Vec<f64>`, `Vec<u8>`, dictionary-encoded strings with
  a lowercased dictionary built at load, and CSR tags. It runs once on a 1-thread rayon pool
  and once on all cores.
- Both sides generate identical data from the same PRNG. Every op prints
  `count/entries/hash` of its result (filtered slots, sorted order, or the DFS of the group
  tree), and the report checks that all implementations agree.

Not included: column download, Vue state/events, clusters, sha1 piles, plugin search and
incremental `updateSelection`. The cost of moving data to the webview has its own bench, see
[Wire](#wire-full-column-stream-vs-windows) below.

```sh
./run.sh 1000000                          # rust, node (V8), jsc (JavaScriptCore), node raw store
NO_RAW=1 ./run.sh 10000000 --reps=2       # extra args go to every engine
node js/bench.js --n=200000 --only="sort" # one engine, a subset of ops
./rust/target/release/collection-bench --n=200000 --threads=1,4
```

`jsc` is the macOS JavaScriptCore shell, the engine inside the Tauri webview on macOS.
Results are written to `results/<impl>-<n>.jsonl`, and `node report.js results <n>` prints
the table.

## Wire: full-column stream vs windows

`./wire.sh 1000000` compares what the webview receives today with a windowed protocol, at
the same N and on the same data:

- **stream**: today's `/instances/column/{id}` NDJSON, one file per column, byte for byte
  what `get_property_column` sends: 10k-row batches, every value as its own JSON text, slots
  with no value left out. `py/stream_encode.py` re-encodes it with msgspec and checks that the
  output is byte-identical. `js/wire.js` ingests it the way `requireFullColumn` does (JSON.parse
  per line, then keysToCamel, JSON.parse per value, writeSlot, buildCSR).
- **window**: rows `[N/2, N/2 + w)` of the collection sorted by label, then score desc, with
  every property, as row objects or as columns, in JSON and msgpack (`--win=200,500`).
- **page**: 50 display lines from the middle of a group tree (group headers, plus rows of 10
  image ids), with the values of those images. `layout` is the one-off flattening of the tree
  into lines, after which each page is a binary search.
- **headers**: every group header of a tree, the data the front needs to size the scroll.

Encoding is timed in Rust (serde_json, rmp-serde) and, for the stream only, in Python (msgspec).
Decoding is timed in V8 and JSC with `JSON.parse`, msgpackr and @msgpack/msgpack, using their
browser builds. Every msgpack payload is checked to decode to the same value as its JSON
twin. Not measured: transport (HTTP or Tauri IPC), UTF-8 decoding of the response, SQLite
reads, and the Pinia store and rAF yields of the real ingest. So the stream numbers are a
lower bound.

Payloads are written to `results/wire/<n>/` (158 MB at 1M, gitignored). Timings go to
`results/wire/<impl>-<n>.jsonl` and the report to `results/wire/report-<n>.md`.

### 1M results (`results/wire/report-1000000.md`)

| | bytes | server encode | JSC decode / ingest |
|---|---:|---:|---:|
| all 7 columns, today's stream | 156.6 MB | 128 ms (msgspec) | 1.43 s |
| 200-row window, JSON rows | 26 KB | 27 µs | 71 µs |
| 500-row window, JSON rows | 65 KB | 68 µs | 166 µs |
| 500-row window, JSON cols | 50 KB | 43 µs | 112 µs |
| 500-row window, msgpack cols (msgpackr) | 35 KB | 25 µs | 125 µs |
| group page, tags tree, 500 images, JSON cols | 55 KB | 61 µs | 132 µs |
| all 3,612 headers of label > year, JSON | 177 KB | 220 µs | 321 µs |

- A window or page costs 0.1–0.4 ms end to end without transport, about 1/7,000 of today's
  full load. The whole budget fits well inside a frame.
- The layout matters more than the format. Columns are about 25% smaller and 30% faster to
  decode than row objects, in both formats. msgpack saves 30–35% of the bytes but is not faster
  to decode in JSC: `JSON.parse` matches msgpackr on columns, beats it on row objects, and takes
  about 1/3 the time on the many small header objects. @msgpack/msgpack is slower than msgpackr
  everywhere.
- Today's load is spent in the webview, not the server. The JSC ingest (per-value
  `JSON.parse`, date parsing) is 11× msgspec's encode time.
- Headers cost about 50 B per group. They are cheap for label and tag trees, but a tree with
  ~N groups (group by text) would need its headers paged too.

## Load: a full column into the Rust engine vs the Python route

`./load.sh 1000000` builds a real `data.db` once per N (schema created by the Python
`DataWriter`, filled with the same synthetic data by `load/`) and loads every column from it
both ways:

- **Rust** (`load/`): a prototype column store (`load/src/store.rs`, `js.rs`, `schema.rs`),
  on one long-lived read connection. `typed` builds the typed column directly from the rows
  (numbers as SQLite hands them, strings interned without a `serde_json::Value`, tags
  counting-sorted into CSR) and applies `SetColumn`. `generic` goes through the delta path
  of the prototype: `serde_json::Value` → `CellValue::from_json` → `SetValues`. `sqlite` is the
  query alone. Every column is checked against the generated data, and `typed` = `generic`.
- **Python** (`py/column_load.py`): the real `get_property_column` and `stream_instances_base`
  routes, imported as they are with a stub `Project`. The body is iterated in process the way
  Starlette does it, so there is no HTTP. `sqlite` is the route's query alone through the same
  `DataReader`. `--dump` writes the bytes, and `js/wire.js` times the JSC ingest of exactly
  those bytes.

Timings go to `results/load/<impl>-<n>.jsonl` and the report to `results/load/report-<n>.md`.

### 1M results (`results/load/report-1000000.md`)

| | Rust engine (typed) | Python route | route + JSC ingest (today) |
|---|---:|---:|---:|
| base (ids, sha1s, file ids) | 276 ms | 629 ms | — |
| one scalar column (label, number, score, checkbox) | 84–98 ms | 571–603 ms | 0.68–0.81 s |
| text (~1M distinct strings) | 253 ms | 623 ms | 831 ms |
| date | 129 ms | 618 ms | 950 ms |
| tags (2.5M rows) | 182 ms | 1.68 s | 1.89 s |
| all 7 columns | 916 ms | 5.27 s | 6.58 s |

- The Rust engine loads the 7 columns 5.8× faster than the Python route alone takes to produce
  them, and 7.2× faster than today's full path to a usable column (route + webview ingest).
  HTTP and the transfer of the 153 MB come on top of that path.
- Python's time goes into the `sqlite3` module, not into the encoding. The bare query with
  `fetchmany` takes 3.95 s of the 5.27 s, against 572 ms for the same queries from Rust. msgspec
  adds about 120 ms per column.
- On the Rust side, SQLite is most of a scalar column (65–70 ms of 85 ms). What remains is
  string interning: the 1M unique sha1s of `base` and the ~1M distinct `text` values cost
  150–200 ms more than the query. The generic delta path costs about 2× typed (1.70 s for all
  7), so an initial load should build columns directly.
- The `value` column is declared `JSON`, which SQLite gives NUMERIC affinity. Numbers come back
  as INTEGER/REAL and the route sends them as JSON numbers, not as JSON texts. The wire bench's
  number streams quote them, so they are about 20% larger than what the route really sends.
  Text, label, date and checkbox streams are byte-identical to the wire bench's.
- Bug found by the bench: the tags branch of `get_property_column` flushes a batch as soon as it
  holds 10k instances, even mid-instance. The next rows of that instance start the next batch,
  and the front's `writeSlot` replaces the tag list. At 1M, 67 instances are sent twice and
  keep only their last tags.

## Lines: scroller layout, front vs engine

`./lines.sh 1000000` times how the two scrollers lay out their lines, with the **real front
code**, and the same layout done in Rust over the engine's own group tree:

- **grid view** = `TreeScroller`: `TreeGeometry` turns the width, image size and depth into images
  per line and a line height (`fillWidths`, `cardLineSize`); `treeSource` gives every group a
  header and every open leaf `ceil(positions / perLine)` lines. Widths 800 / 1440 / 2560 px,
  images 100 / 200 px, 2 properties per card.
- **table** = `GridScroller`: `gridSource` gives every leaf a header and one row per image (or
  pile), at the `rowSize` estimate (104 px with images, 28 px without). Rows are measured on screen.

`js/build-front-lines.js` type-strips `scrollLayout.ts`, `treeLines.ts`, `gridLines.ts` and
`sha1Piles.ts` with the front's TypeScript into `js/dist/front-lines.js` (gitignored); they only
have type imports, so they run unchanged. `js/lines.js` loads `bench.js` as a library for the data
and the group trees (built outside the timings) and drives `ScrollLayout` the way the scrollers
and `VirtualScroller` do. `rust/src/lines.rs` (`--lines`) ports `ScrollLayout` (heights, one
Fenwick tree per inner node, measured bodies) onto the tree's own node indices.

Trees: flat, label > date by year, tags (+ parents), text (~N groups), and label > year in sha1
mode (synthetic sha1s, ~30% duplicates). Ops:

| op | what it is in the app |
|---|---|
| build | `layout.rebuild()`, on every new result |
| resize / row size | `geometry.setParams()` + `layout.refresh()`, on a width or image-size change |
| toggle one | close + open one group, `refreshNode` |
| close all / open all | flip every `view.closed` + `layout.refresh()` |
| locate / offsetOf | pixel → line and line → pixel, per call |
| window | one `VirtualScroller.update` walk (1000 px + 300 px overscan) making its line objects |
| all lines | every line object of the whole list: the eager way, for comparison |
| measure screen | table: `setMeasured` on one screen of rows of a fresh layout |

Every implementation must produce the same line count, total height and line-list hash per
(tree, view, config), and the same hashes for locate, offsetOf and window. They do at 20k, 100k
and 1M (0 mismatches). Results go to `results/lines/<impl>-<n>.jsonl`, and the report to
`results/lines/report-<n>.md`.

Left out: Vue (the bench calls the sources on plain objects: if the manager reaches the scroller
through a reactive proxy, every source call pays a proxy get), DOM work, rendering and
`ScrollPager` (for lists taller than the browser's maximum element height).

### 1M, JSC (the webview) vs Rust (8 threads)

| | groups | build | resize | close / open all | window | all lines, eager |
|---|---:|---:|---:|---:|---:|---:|
| grid, flat | 0 | 3.7 µs / 41 ns | 1 µs / 42 ns | — | 2.2 µs / 125 ns | 11 ms / 0.6 ms (167k lines) |
| grid, label > year | 3.6k | 0.55 ms / 24 µs | 0.23 ms / 24 µs | 0.5 ms / 23 µs | 2.0 µs / 0.5 µs | 9.3 ms / 0.34 ms |
| grid, tags | 1k | 0.14 ms / 9 µs | 74 µs / 9 µs | 0.16 ms / 8 µs | 1.2 µs / 0.4 µs | 50 ms / 2.4 ms (773k lines) |
| grid, text | 920k | 650 ms / 6.7 ms | 541 ms / 6.5 ms | 0.68 s / 6.5 ms | 6.1 µs / 1.4 µs | 0.67 s / 7.6 ms (1.85M lines) |
| table, flat | 0 | 2.2 µs / 41 ns | 1 µs / 42 ns | — | 3.2 µs / 0.46 µs | 53 ms / 4.9 ms (1M rows) |
| table, tags | 1k | 0.12 ms / 9 µs | 60 µs / 9 µs | 0.14 ms / 8 µs | 4.2 µs / 0.9 µs | 0.26 s / 13 ms (4.6M rows) |
| table, text | 920k | 627 ms / 6.6 ms | 520 ms / 6.3 ms | 0.68 s / 6.4 ms | 14 µs / 2.8 µs | 0.87 s / 9.3 ms |

- The front layout costs O(groups), never O(images). With up to a few thousand groups, every op
  stays under 1 ms in JSC, resize included. Only a tree with ~N groups (text) freezes the UI:
  about 0.5–0.7 s for each rebuild, resize or open/close all.
- Building every line object is the expensive path, and the current lazy code never does it. A
  window costs 1–14 µs.
- In Rust, the same layout takes 6–9 ms for 920k groups at 1M, and 63–91 ms for 9.2M groups at
  10M. Threads only help on trees that large. `measure screen` on a flat table is O(rows of the
  leaf): 1.1 ms at 1M in JSC, 5 ms at 10M in Rust.
