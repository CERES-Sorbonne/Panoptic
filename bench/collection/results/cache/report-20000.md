# Cold column load, N = 20,000

`cache.db` = the load bench's data.db plus a `column_cache` table: 15.2 MB file, blobs
1.6 MB raw / 712 kB zstd for all columns. **Cold** = a fresh copy of
cache.db written with F_NOCACHE before each rep: at most 0.0% of its pages were in the OS cache
after the copy (mincore). Open, schema and identity are read untimed, then one column is loaded.
**Warm** = the same load again on that connection. `typed` = rows → column (today's prototype
load), `sqlite` = the rows only, `blob` = cached column blob → column. Medians of 2.

| column | sqlite cold | typed cold | blob cold | zstd cold | typed warm | blob warm | zstd warm | blob | zstd blob | typed / blob cold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| text | 4.0 ms | 5.1 ms | 3.4 ms | 3.7 ms | 2.6 ms | 1.4 ms | 2.0 ms | 703 kB | 271 kB | 1.5× |
| label | 3.2 ms | 3.5 ms | 1.4 ms | 1.5 ms | 1.2 ms | 0.05 ms | 0.20 ms | 83 kB | 31 kB | 2.4× |
| number | 3.0 ms | 3.1 ms | 1.2 ms | 1.3 ms | 0.91 ms | 0.03 ms | 0.17 ms | 160 kB | 51 kB | 2.6× |
| score | 3.3 ms | 3.2 ms | 1.2 ms | 1.3 ms | 0.97 ms | 0.01 ms | 0.11 ms | 160 kB | 117 kB | 2.7× |
| date | 4.0 ms | 4.4 ms | 1.2 ms | 1.3 ms | 1.3 ms | 0.09 ms | 0.19 ms | 160 kB | 113 kB | 3.8× |
| checkbox | 3.2 ms | 3.3 ms | 1.2 ms | 1.3 ms | 1.0 ms | 0.03 ms | 0.03 ms | 20 kB | 5 kB | 2.8× |
| tags | 8.0 ms | 8.4 ms | 1.3 ms | 1.6 ms | 2.5 ms | 0.04 ms | 0.28 ms | 281 kB | 126 kB | 6.5× |
| **sum** | **29 ms** | **31 ms** | **11 ms** | **12 ms** | **11 ms** | **1.7 ms** | **3.0 ms** | | | **2.9×** |

## Whole project open, cold

Fresh cold copy, then connection + schema + identity + every column, timed together.

| columns from | time | vs typed |
|---|---:|---:|
| typed | 36 ms | 1.0× |
| blob | 13 ms | 2.8× |
| blob-zstd | 15 ms | 2.5× |
