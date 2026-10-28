
N = 50,000  (MB = 2^20 bytes)

### Loaded columns

|  | v8 | jsc | v8-raw | rust-1t | rust-8t |
|---|---:|---:|---:|---:|---:|
| live data (heap after GC) | 12.5 MB | 7.5 MB | 12.5 MB | 6.8 MB | 6.8 MB |
| process footprint once loaded | 50.2 MB | 37.8 MB | 35.1 MB | 8.9 MB | 8.9 MB |

### Retained by the result (live heap after GC, result held)

| op | v8 | jsc | v8-raw | rust-1t | v8 vs rust-1t | jsc vs rust-1t | same result |
|---|---:|---:|---:|---:|---:|---:|---:|
| filter: number > 5000 | 0.1 MB | 0.2 MB | 0.1 MB | 0.1 MB | 1.5× | 2.6× | yes |
| filter: number isSet | 0.2 MB | 0.3 MB | 0.2 MB | 0.2 MB | 1.2× | 1.8× | yes |
| filter: score <= 250.5 | 0.1 MB | 0.2 MB | 0.1 MB | ~0 | — | — | yes |
| filter: date > 2020-01-01 | 0.1 MB | 0.2 MB | 0.1 MB | 0.1 MB | 1.5× | 2.6× | yes |
| filter: checkbox isTrue | 0.2 MB | 0.3 MB | 0.1 MB | 0.1 MB | 2.0× | 3.8× | yes |
| filter: text contains | 0.1 MB | 0.2 MB | ~0 | ~0 | — | — | yes |
| filter: text startsWith | 0.1 MB | 0.2 MB | ~0 | ~0 | — | — | yes |
| filter: text like (regex) | 0.1 MB | 0.3 MB | ~0 | ~0 | — | — | yes |
| filter: label equal | 0.1 MB | 0.2 MB | ~0 | ~0 | — | — | yes |
| filter: tags containsAny | 0.1 MB | 0.3 MB | ~0 | ~0 | — | — | yes |
| filter: tags containsNot | 0.3 MB | 0.4 MB | 0.2 MB | 0.2 MB | 1.5× | 2.4× | yes |
| filter: search box (text+tags) | 0.1 MB | 0.2 MB | ~0 | ~0 | — | — | yes |
| filter: compound and/or | 0.1 MB | 0.3 MB | 0.1 MB | ~0 | — | — | yes |
| sort: number | 0.2 MB | 0.4 MB | 0.2 MB | 0.2 MB | 1.2× | 1.9× | yes |
| sort: score (float) desc | 0.2 MB | 0.4 MB | 0.2 MB | 0.2 MB | 1.2× | 1.9× | yes |
| sort: date | 0.2 MB | 0.4 MB | 0.2 MB | 0.2 MB | 1.2× | 1.9× | yes |
| sort: text | 0.3 MB | 7.5 MB | 0.2 MB | 0.2 MB | 1.5× | 39× | yes |
| sort: tags (count) | 0.3 MB | 0.4 MB | 0.2 MB | 0.2 MB | 1.5× | 2.2× | yes |
| sort: label, score desc | 0.3 MB | 2.8 MB | 0.2 MB | 0.2 MB | 1.5× | 15× | yes |
| group: number (10k values) | 18.0 MB | 28.2 MB | 18.0 MB | 1.5 MB | 12× | 18× | yes |
| group: date by month | 10.3 MB | 19.6 MB | 10.3 MB | 0.8 MB | 13× | 25× | yes |
| group: label (300 values) | 10.5 MB | 19.7 MB | 10.4 MB | 0.8 MB | 13× | 25× | yes |
| group: checkbox | 10.1 MB | 19.5 MB | 10.1 MB | 0.8 MB | 13× | 26× | yes |
| group: tags (+parents) | 15.5 MB | 36.4 MB | 15.5 MB | 2.2 MB | 7.0× | 16× | yes |
| group: label > date by year | 14.0 MB | 23.5 MB | 14.0 MB | 1.2 MB | 12× | 20× | yes |
| group: text (~N values) | 47.1 MB | 61.5 MB | 47.1 MB | 3.8 MB | 12× | 16× | yes |
| pipeline: compound > sort > tags | 3.1 MB | 6.9 MB | 3.0 MB | 0.5 MB | 5.7× | 13× | yes |

### Peak during the op (process footprint above the footprint once loaded)

| op | v8 | jsc | v8-raw | rust-1t | rust-8t | rust-1t heap peak | rust-8t heap peak |
|---|---:|---:|---:|---:|---:|---:|---:|
| filter: number > 5000 | 6.8 MB | 2.8 MB | 5.2 MB | ~0 | 0.9 MB | 0.3 MB | 0.3 MB |
| filter: number isSet | 0.9 MB | 2.7 MB | 4.6 MB | ~0 | 0.9 MB | 0.5 MB | 0.5 MB |
| filter: score <= 250.5 | 0.6 MB | 2.7 MB | 5.3 MB | ~0 | 0.6 MB | 0.2 MB | 0.2 MB |
| filter: date > 2020-01-01 | 0.7 MB | 2.7 MB | 5.2 MB | ~0 | 0.6 MB | 0.3 MB | 0.3 MB |
| filter: checkbox isTrue | 22.3 MB | 32.9 MB | 4.1 MB | 0.8 MB | 0.8 MB | 0.3 MB | 0.3 MB |
| filter: text contains | 22.1 MB | 34.1 MB | 6.4 MB | ~0 | 0.6 MB | 0.1 MB | 0.1 MB |
| filter: text startsWith | 29.5 MB | 34.1 MB | 7.3 MB | 0.5 MB | 0.6 MB | 0.1 MB | 0.1 MB |
| filter: text like (regex) | 28.8 MB | 35.5 MB | 8.4 MB | 1.0 MB | 1.4 MB | 0.4 MB | 0.4 MB |
| filter: label equal | 28.8 MB | 33.6 MB | 5.0 MB | 0.7 MB | 0.5 MB | ~0 | 0.1 MB |
| filter: tags containsAny | 21.2 MB | 33.9 MB | 6.7 MB | ~0 | 0.6 MB | 0.1 MB | 0.1 MB |
| filter: tags containsNot | 28.7 MB | 35.3 MB | 6.4 MB | ~0 | 1.0 MB | 0.5 MB | 0.5 MB |
| filter: search box (text+tags) | 23.2 MB | 39.2 MB | 16.4 MB | 0.6 MB | 0.7 MB | 0.1 MB | 0.1 MB |
| filter: compound and/or | 24.4 MB | 35.9 MB | 11.9 MB | 0.7 MB | 0.8 MB | 0.2 MB | 0.2 MB |
| sort: number | 9.9 MB | 7.2 MB | 15.0 MB | 1.8 MB | 2.0 MB | 1.3 MB | 1.3 MB |
| sort: score (float) desc | 16.3 MB | 15.0 MB | 22.1 MB | 0.4 MB | 1.7 MB | 1.3 MB | 1.3 MB |
| sort: date | 23.7 MB | 15.8 MB | 22.1 MB | 0.4 MB | 1.9 MB | 1.3 MB | 1.3 MB |
| sort: text | 38.6 MB | 50.2 MB | 20.0 MB | ~0 | 1.8 MB | 1.0 MB | 1.0 MB |
| sort: tags (count) | 23.4 MB | 34.0 MB | 14.1 MB | ~0 | 1.2 MB | 1.0 MB | 1.0 MB |
| sort: label, score desc | 31.8 MB | 49.9 MB | 26.1 MB | 2.0 MB | 2.3 MB | 1.7 MB | 1.7 MB |
| group: number (10k values) | 45.3 MB | 43.5 MB | 53.2 MB | 3.2 MB | 3.4 MB | 1.9 MB | 1.9 MB |
| group: date by month | 27.2 MB | 35.3 MB | 30.4 MB | ~0 | 1.8 MB | 1.0 MB | 1.0 MB |
| group: label (300 values) | 18.5 MB | 28.1 MB | 29.0 MB | 0.1 MB | 1.3 MB | 1.0 MB | 1.0 MB |
| group: checkbox | 29.6 MB | 26.8 MB | 29.4 MB | ~0 | 0.9 MB | 1.0 MB | 1.0 MB |
| group: tags (+parents) | 34.1 MB | 73.8 MB | 43.4 MB | 0.1 MB | 1.1 MB | 2.4 MB | 2.4 MB |
| group: label > date by year | 43.6 MB | 43.9 MB | 46.0 MB | 0.5 MB | 3.6 MB | 1.4 MB | 1.4 MB |
| group: text (~N values) | 107 MB | 102 MB | 104 MB | 6.7 MB | 7.4 MB | 5.1 MB | 5.1 MB |
| pipeline: compound > sort > tags | 27.9 MB | 45.5 MB | 27.0 MB | 1.5 MB | 1.3 MB | 0.8 MB | 0.8 MB |
| **max** | **107 MB** | **102 MB** | **104 MB** | **6.7 MB** | **7.4 MB** | **5.1 MB** | **5.1 MB** |
