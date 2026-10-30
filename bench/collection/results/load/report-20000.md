
# Full column load, N = 20,000

Same data.db (Python schema, warm OS cache) for both sides. Rust = the prototype store
(`load/src/store.rs`) on one long-lived read connection: `typed` builds the column directly,
`generic` goes through `serde_json::Value` + `CellValue::from_json` + `SetValues`. Python =
the real route, body iterated in-process (no HTTP), new reader per request as in the app.
JSC = the webview ingest (`js/wire.js`) of the bytes that route produced. Medians.

| column | rows | rust sqlite | rust typed | rust generic | py sqlite | py route | route bytes | jsc ingest | today (route + jsc) | route / typed | today / typed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base | 20,000 | 1.3 ms | 4.1 ms | — | 11 ms | 14 ms | 1.0 MB | n/a | 14 ms | 3.3× | — |
| text | 18,441 | 1.6 ms | 2.8 ms | 4.5 ms | 11 ms | 14 ms | 761.6 KB | 3.4 ms | 18 ms | 5.1× | 6.4× |
| label | 17,975 | 1.4 ms | 1.7 ms | 3.3 ms | 10 ms | 14 ms | 325.5 KB | 2.5 ms | 16 ms | 8.0× | 9.5× |
| number | 19,004 | 1.2 ms | 1.3 ms | 2.1 ms | 9.9 ms | 13 ms | 192.7 KB | 1.1 ms | 14 ms | 10× | 11× |
| score | 18,986 | 1.3 ms | 1.4 ms | 2.3 ms | 10 ms | 14 ms | 438.6 KB | 1.9 ms | 15 ms | 9.7× | 11× |
| date | 19,014 | 1.4 ms | 2.2 ms | 3.6 ms | 11 ms | 14 ms | 677.6 KB | 5.0 ms | 19 ms | 6.3× | 8.5× |
| checkbox | 18,005 | 1.4 ms | 1.4 ms | 2.4 ms | 10 ms | 13 ms | 228.5 KB | 1.5 ms | 15 ms | 9.4× | 10× |
| tags | 50,124 | 2.9 ms | 3.1 ms | 6.2 ms | 22 ms | 35 ms | 331.3 KB | 3.1 ms | 38 ms | 11× | 12× |
| **all 7 columns** |  | **11 ms** | **14 ms** | **24 ms** | **84 ms** | **116 ms** | **2.9 MB** | **18 ms** | **135 ms** | **8.3×** | **9.7×** |

⚠ tags: the route sent 16,745 ids for 16,744 instances (an instance split across two batches).

