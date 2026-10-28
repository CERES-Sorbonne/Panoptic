
N = 1,000,000  (median ms)

| op | v8 | jsc | v8-raw | rust-1t | rust-8t | rust-8t vs v8 | rust-8t vs jsc | same result |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| filter: number > 5000 | 17 ms | 12 ms | 16 ms | 8.5 ms | 1.8 ms | 9.4× | 6.7× | yes |
| filter: number isSet | 8.1 ms | 3.9 ms | 7.9 ms | 2.9 ms | 0.9 ms | 8.7× | 4.2× | yes |
| filter: score <= 250.5 | 12 ms | 13 ms | 11 ms | 4.7 ms | 1.0 ms | 12× | 13× | yes |
| filter: date > 2020-01-01 | 16 ms | 32 ms | 17 ms | 8.1 ms | 1.6 ms | 9.8× | 19× | yes |
| filter: checkbox isTrue | 369 ms | 216 ms | 20 ms | 7.1 ms | 1.7 ms | 222× | 129× | yes |
| filter: text contains | 408 ms | 280 ms | 58 ms | 6.6 ms | 1.5 ms | 271× | 186× | yes |
| filter: text startsWith | 385 ms | 254 ms | 39 ms | 5.5 ms | 1.5 ms | 255× | 168× | yes |
| filter: text like (regex) | 484 ms | 256 ms | 126 ms | 13 ms | 11 ms | 46× | 24× | yes |
| filter: label equal | 375 ms | 210 ms | 29 ms | 1.7 ms | 0.5 ms | 717× | 402× | yes |
| filter: tags containsAny | 413 ms | 234 ms | 60 ms | 8.5 ms | 1.9 ms | 222× | 126× | yes |
| filter: tags containsNot | 406 ms | 231 ms | 59 ms | 9.6 ms | 2.8 ms | 144× | 82× | yes |
| filter: search box (text+tags) | 1.27 s | 5.52 s | 191 ms | 15 ms | 3.2 ms | 399× | 1729× | yes |
| filter: compound and/or | 429 ms | 311 ms | 81 ms | 29 ms | 5.9 ms | 72× | 53× | yes |
| sort: number | 174 ms | 193 ms | 176 ms | 29 ms | 7.6 ms | 23× | 25× | yes |
| sort: score (float) desc | 589 ms | 343 ms | 589 ms | 30 ms | 7.4 ms | 80× | 47× | yes |
| sort: date | 589 ms | 340 ms | 583 ms | 30 ms | 7.3 ms | 81× | 47× | yes |
| sort: text | 1.27 s | 2.18 s | 921 ms | 175 ms | 63 ms | 20× | 34× | yes |
| sort: tags (count) | 487 ms | 347 ms | 141 ms | 25 ms | 6.4 ms | 76× | 54× | yes |
| sort: label, score desc | 1.04 s | 1.73 s | 704 ms | 33 ms | 8.2 ms | 128× | 212× | yes |
| group: number (10k values) | 346 ms | 230 ms | 347 ms | 31 ms | 19 ms | 18× | 12× | yes |
| group: date by month | 385 ms | 253 ms | 382 ms | 15 ms | 9.3 ms | 41× | 27× | yes |
| group: label (300 values) | 316 ms | 230 ms | 317 ms | 8.3 ms | 8.2 ms | 38× | 28× | yes |
| group: checkbox | 275 ms | 175 ms | 270 ms | 9.0 ms | 6.4 ms | 43× | 27× | yes |
| group: tags (+parents) | 1.52 s | 1.85 s | 1.44 s | 84 ms | 34 ms | 45× | 55× | yes |
| group: label > date by year | 533 ms | 350 ms | 534 ms | 24 ms | 14 ms | 39× | 26× | yes |
| group: text (~N values) | 4.94 s | 4.85 s | 4.08 s | 341 ms | 107 ms | 46× | 45× | yes |
| pipeline: compound > sort > tags | 915 ms | 1.54 s | 388 ms | 51 ms | 19 ms | 48× | 80× | yes |
| **total** | **17.97 s** | **22.18 s** | **11.59 s** | **1.01 s** | **352 ms** | **51×** | **63×** | |
