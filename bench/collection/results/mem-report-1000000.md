
N = 1,000,000  (MB = 2^20 bytes)

### Loaded columns

|  | v8 | jsc | v8-raw | rust-1t | rust-8t |
|---|---:|---:|---:|---:|---:|
| live data (heap after GC) | 241 MB | 142 MB | 241 MB | 134 MB | 134 MB |
| process footprint once loaded | 325 MB | 264 MB | 314 MB | 124 MB | 124 MB |

### Retained by the result (live heap after GC, result held)

| op | v8 | jsc | v8-raw | rust-1t | v8 vs rust-1t | jsc vs rust-1t | same result |
|---|---:|---:|---:|---:|---:|---:|---:|
| filter: number > 5000 | 1.9 MB | 1.9 MB | 1.8 MB | 1.8 MB | 1.0× | 1.1× | yes |
| filter: number isSet | 3.7 MB | 3.7 MB | 3.6 MB | 3.6 MB | 1.0× | 1.0× | yes |
| filter: score <= 250.5 | 1.0 MB | 1.0 MB | 0.9 MB | 0.9 MB | 1.0× | 1.1× | yes |
| filter: date > 2020-01-01 | 1.9 MB | 1.9 MB | 1.8 MB | 1.8 MB | 1.0× | 1.1× | yes |
| filter: checkbox isTrue | 1.8 MB | 1.9 MB | 1.7 MB | 1.7 MB | 1.0× | 1.1× | yes |
| filter: text contains | 0.1 MB | 0.2 MB | 0.1 MB | ~0 | — | — | yes |
| filter: text startsWith | 0.2 MB | 0.3 MB | 0.1 MB | 0.1 MB | 1.8× | 3.0× | yes |
| filter: text like (regex) | 1.1 MB | 0.2 MB | ~0 | ~0 | — | — | yes |
| filter: label equal | 0.1 MB | 0.2 MB | ~0 | ~0 | — | — | yes |
| filter: tags containsAny | 0.3 MB | 0.4 MB | 0.2 MB | 0.2 MB | 1.6× | 2.4× | yes |
| filter: tags containsNot | 3.6 MB | 3.7 MB | 3.5 MB | 3.5 MB | 1.0× | 1.1× | yes |
| filter: search box (text+tags) | 0.1 MB | 0.1 MB | 0.1 MB | ~0 | — | — | yes |
| filter: compound and/or | 0.6 MB | 0.8 MB | 3.9 MB | 0.5 MB | 1.3× | 1.5× | yes |
| sort: number | 19.1 MB | 4.0 MB | 19.1 MB | 3.8 MB | 5.0× | 1.0× | yes |
| sort: score (float) desc | 3.9 MB | 4.0 MB | 3.8 MB | 3.8 MB | 1.0× | 1.0× | yes |
| sort: date | 3.9 MB | 4.0 MB | 3.8 MB | 3.8 MB | 1.0× | 1.0× | yes |
| sort: text | 3.9 MB | 4.0 MB | 3.9 MB | 3.8 MB | 1.0× | 1.1× | yes |
| sort: tags (count) | 11.5 MB | 4.0 MB | 11.5 MB | 3.8 MB | 3.0× | 1.1× | yes |
| sort: label, score desc | 3.9 MB | 4.0 MB | 3.9 MB | 3.8 MB | 1.0× | 1.1× | yes |
| group: number (10k values) | 206 MB | 374 MB | 206 MB | 16.0 MB | 13× | 23× | yes |
| group: date by month | 198 MB | 364 MB | 198 MB | 15.3 MB | 13× | 24× | yes |
| group: label (300 values) | 199 MB | 367 MB | 199 MB | 15.3 MB | 13× | 24× | yes |
| group: checkbox | 197 MB | 425 MB | 197 MB | 15.3 MB | 13× | 28× | yes |
| group: tags (+parents) | 290 MB | 685 MB | 290 MB | 43.0 MB | 6.7× | 16× | yes |
| group: label > date by year | 211 MB | 379 MB | 211 MB | 17.5 MB | 12× | 22× | yes |
| group: text (~N values) | 935 MB | 1179 MB | 935 MB | 89.3 MB | 10× | 13× | yes |
| pipeline: compound > sort > tags | 47.1 MB | 98.7 MB | 47.0 MB | 9.4 MB | 5.0× | 11× | yes |

### Peak during the op (process footprint above the footprint once loaded)

| op | v8 | jsc | v8-raw | rust-1t | rust-8t | rust-1t heap peak | rust-8t heap peak |
|---|---:|---:|---:|---:|---:|---:|---:|
| filter: number > 5000 | 16.3 MB | 11.7 MB | 11.5 MB | 4.0 MB | 10.1 MB | 4.8 MB | 4.8 MB |
| filter: number isSet | 13.0 MB | 11.9 MB | 12.7 MB | 4.0 MB | 10.0 MB | 8.6 MB | 8.6 MB |
| filter: score <= 250.5 | 13.6 MB | 11.7 MB | 13.2 MB | 4.0 MB | 3.9 MB | 2.9 MB | 2.9 MB |
| filter: date > 2020-01-01 | 11.0 MB | 12.3 MB | 14.3 MB | 3.9 MB | 8.2 MB | 4.8 MB | 4.8 MB |
| filter: checkbox isTrue | 14.2 MB | 456 MB | 10.7 MB | 4.0 MB | 8.9 MB | 4.7 MB | 4.7 MB |
| filter: text contains | 29.0 MB | 478 MB | 25.9 MB | 4.0 MB | 4.8 MB | 1.8 MB | 1.8 MB |
| filter: text startsWith | 29.6 MB | 479 MB | 24.7 MB | 4.0 MB | 4.9 MB | 1.8 MB | 1.8 MB |
| filter: text like (regex) | 13.8 MB | 477 MB | 26.0 MB | 4.1 MB | 7.5 MB | 1.9 MB | 2.0 MB |
| filter: label equal | 15.7 MB | 450 MB | 21.0 MB | 4.0 MB | 1.6 MB | 1.0 MB | 1.0 MB |
| filter: tags containsAny | 26.7 MB | 449 MB | 17.2 MB | 12.0 MB | 10.1 MB | 1.4 MB | 1.4 MB |
| filter: tags containsNot | 26.2 MB | 449 MB | 18.4 MB | 13.9 MB | 17.4 MB | 8.5 MB | 8.5 MB |
| filter: search box (text+tags) | 27.0 MB | 538 MB | 20.6 MB | 12.0 MB | 12.9 MB | 1.8 MB | 1.8 MB |
| filter: compound and/or | 30.3 MB | 478 MB | 30.0 MB | 15.8 MB | 16.9 MB | 3.7 MB | 3.7 MB |
| sort: number | 52.2 MB | 69.0 MB | 55.5 MB | 15.3 MB | 12.1 MB | 26.7 MB | 26.7 MB |
| sort: score (float) desc | 186 MB | 311 MB | 173 MB | 4.1 MB | 16.0 MB | 26.7 MB | 26.7 MB |
| sort: date | 185 MB | 312 MB | 184 MB | 4.0 MB | 12.1 MB | 26.7 MB | 26.7 MB |
| sort: text | 204 MB | 778 MB | 208 MB | 11.7 MB | 22.7 MB | 19.1 MB | 19.1 MB |
| sort: tags (count) | 55.2 MB | 462 MB | 54.3 MB | 4.1 MB | 18.9 MB | 19.1 MB | 19.1 MB |
| sort: label, score desc | 188 MB | 830 MB | 198 MB | 4.0 MB | 23.7 MB | 34.3 MB | 34.3 MB |
| group: number (10k values) | 304 MB | 500 MB | 292 MB | 7.9 MB | 31.6 MB | 22.0 MB | 22.0 MB |
| group: date by month | 287 MB | 630 MB | 294 MB | 7.9 MB | 20.0 MB | 19.1 MB | 19.1 MB |
| group: label (300 values) | 284 MB | 487 MB | 278 MB | 11.8 MB | 16.4 MB | 19.1 MB | 19.1 MB |
| group: checkbox | 283 MB | 469 MB | 281 MB | 11.7 MB | 8.3 MB | 19.1 MB | 19.1 MB |
| group: tags (+parents) | 574 MB | 979 MB | 562 MB | 12.1 MB | 24.7 MB | 46.9 MB | 46.9 MB |
| group: label > date by year | 316 MB | 642 MB | 311 MB | 18.5 MB | 21.9 MB | 21.4 MB | 21.4 MB |
| group: text (~N values) | 1658 MB | 1859 MB | 1667 MB | 64.0 MB | 75.9 MB | 139 MB | 139 MB |
| pipeline: compound > sort > tags | 105 MB | 582 MB | 101 MB | 23.4 MB | 26.4 MB | 14.2 MB | 14.2 MB |
| **max** | **1658 MB** | **1859 MB** | **1667 MB** | **64.0 MB** | **75.9 MB** | **139 MB** | **139 MB** |
