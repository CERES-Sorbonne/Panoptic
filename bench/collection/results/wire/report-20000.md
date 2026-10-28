
# Wire cost, N = 20,000

Encode: Python = msgspec.json.encode of the prebuilt line structs (what get_property_column
runs per batch, SQLite read and list building excluded); Rust = serde_json / rmp-serde,
building the window from the columns included. Decode: V8 = node, JSC = macOS jsc shell
(the Tauri webview engine). Transport is not measured. Medians.

## Today: `/instances/column/{id}` NDJSON, whole column

| column | kind | bytes | encode py | encode rust | ingest v8 | ingest jsc | py + jsc |
|---|---:|---:|---:|---:|---:|---:|---:|
| text | string | 761.6 KB | 513 µs | 789 µs | 4.8 ms | 3.7 ms | 4.3 ms |
| label | string | 325.5 KB | 370 µs | 655 µs | 4.0 ms | 2.7 ms | 3.0 ms |
| number | numeric | 229.8 KB | 229 µs | 410 µs | 4.0 ms | 1.9 ms | 2.1 ms |
| score | numeric | 475.7 KB | 289 µs | 508 µs | 4.0 ms | 2.1 ms | 2.3 ms |
| date | date | 677.6 KB | 341 µs | 579 µs | 6.3 ms | 5.3 ms | 5.6 ms |
| checkbox | bool | 228.5 KB | 255 µs | 374 µs | 3.1 ms | 1.5 ms | 1.8 ms |
| tags | tag | 331.3 KB | 312 µs | 430 µs | 4.9 ms | 3.2 ms | 3.5 ms |
| **all 7** |  | **3.0 MB** | **2.3 ms** | **3.7 ms** | **31 ms** | **20 ms** | **23 ms** |

msgspec re-encode is byte-identical to the Rust replica: yes

## Window: rows `[N/2, N/2 + w)` of the collection sorted by label, score desc, all 7 properties

| payload | images | decoder | bytes | encode rust | decode v8 | decode jsc | rust + jsc | same as json |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 200 rows | 200 | JSON.parse | 25.4 KB | 26.8 µs | 70.8 µs | 67.9 µs | 94.7 µs |  |
| 200 rows | 200 | msgpackr | 16.4 KB | 10.2 µs | 76.0 µs | 93.0 µs | 103 µs | yes |
| 200 rows | 200 | @msgpack/msgpack | 16.4 KB | 10.2 µs | 99.9 µs | 139 µs | 149 µs | yes |
| 200 cols | 200 | JSON.parse | 19.5 KB | 17.0 µs | 50.6 µs | 44.2 µs | 61.2 µs |  |
| 200 cols | 200 | msgpackr | 13.2 KB | 9.6 µs | 36.7 µs | 49.8 µs | 59.4 µs | yes |
| 200 cols | 200 | @msgpack/msgpack | 13.2 KB | 9.6 µs | 45.3 µs | 69.1 µs | 78.7 µs | yes |
| 500 rows | 500 | JSON.parse | 63.2 KB | 69.5 µs | 178 µs | 172 µs | 241 µs |  |
| 500 rows | 500 | msgpackr | 40.8 KB | 30.5 µs | 190 µs | 241 µs | 272 µs | yes |
| 500 rows | 500 | @msgpack/msgpack | 40.8 KB | 30.5 µs | 249 µs | 348 µs | 379 µs | yes |
| 500 cols | 500 | JSON.parse | 48.3 KB | 44.1 µs | 128 µs | 113 µs | 157 µs |  |
| 500 cols | 500 | msgpackr | 32.7 KB | 25.1 µs | 92.0 µs | 128 µs | 153 µs | yes |
| 500 cols | 500 | @msgpack/msgpack | 32.7 KB | 25.1 µs | 114 µs | 176 µs | 201 µs | yes |

## Group page: 50 lines (headers + rows of 10 images) from the middle of the tree, plus their values

| payload | images | decoder | bytes | encode rust | decode v8 | decode jsc | rust + jsc | same as json |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| label > date by year rows | 128 | JSON.parse | 18.7 KB | 22.7 µs | 54.9 µs | 49.1 µs | 71.8 µs |  |
| label > date by year rows | 128 | msgpackr | 12.1 KB | 10.6 µs | 58.4 µs | 74.0 µs | 84.6 µs | yes |
| label > date by year rows | 128 | @msgpack/msgpack | 12.1 KB | 10.6 µs | 71.7 µs | 98.9 µs | 109 µs | yes |
| label > date by year cols | 128 | JSON.parse | 15.0 KB | 17.4 µs | 42.0 µs | 33.9 µs | 51.3 µs |  |
| label > date by year cols | 128 | msgpackr | 10.1 KB | 10.4 µs | 33.4 µs | 44.9 µs | 55.3 µs | yes |
| label > date by year cols | 128 | @msgpack/msgpack | 10.1 KB | 10.4 µs | 37.5 µs | 56.9 µs | 67.3 µs | yes |
| tags (+parents) rows | 403 | JSON.parse | 56.2 KB | 67.0 µs | 166 µs | 158 µs | 225 µs |  |
| tags (+parents) rows | 403 | msgpackr | 35.9 KB | 32.1 µs | 169 µs | 214 µs | 246 µs | yes |
| tags (+parents) rows | 403 | @msgpack/msgpack | 35.9 KB | 32.1 µs | 217 µs | 295 µs | 327 µs | yes |
| tags (+parents) cols | 403 | JSON.parse | 43.8 KB | 49.2 µs | 125 µs | 110 µs | 159 µs |  |
| tags (+parents) cols | 403 | msgpackr | 29.3 KB | 29.2 µs | 86.5 µs | 118 µs | 147 µs | yes |
| tags (+parents) cols | 403 | @msgpack/msgpack | 29.3 KB | 29.2 µs | 107 µs | 155 µs | 184 µs | yes |

Line layout of the tree (once per regroup, then every page is a binary search):

| tree | groups | lines | layout rust |
|---|---:|---:|---:|
| label > date by year | 3,589 | 7,172 | 6.0 µs |
| tags (+parents) | 1,001 | 10,836 | 1.5 µs |

## Every group header of the tree (to size the whole scroll)

| payload | groups | decoder | bytes | encode rust | decode v8 | decode jsc | rust + jsc | same as json |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| label > date by year | 3589 | JSON.parse | 168.9 KB | 211 µs | 457 µs | 313 µs | 524 µs |  |
| label > date by year | 3589 | msgpackr | 115.9 KB | 77.7 µs | 747 µs | 883 µs | 961 µs | yes |
| label > date by year | 3589 | @msgpack/msgpack | 115.9 KB | 77.7 µs | 604 µs | 810 µs | 888 µs | yes |
| tags (+parents) | 1001 | JSON.parse | 51.4 KB | 62.1 µs | 167 µs | 117 µs | 179 µs |  |
| tags (+parents) | 1001 | msgpackr | 36.5 KB | 23.2 µs | 224 µs | 278 µs | 301 µs | yes |
| tags (+parents) | 1001 | @msgpack/msgpack | 36.5 KB | 23.2 µs | 207 µs | 299 µs | 322 µs | yes |

## Per scroll vs today

|  | bytes | server + jsc | vs all 7 columns today |
|---|---:|---:|---:|
| all 7 columns, today | 3.0 MB | 23 ms | 1× |
| 500-row window, json rows | 63.2 KB | 241 µs | 1/48 bytes, 1/94 time |
| 500-row window, msgpack cols | 32.7 KB | 153 µs | 1/93 bytes, 1/148 time |

