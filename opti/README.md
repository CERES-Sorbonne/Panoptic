# opti: notes on the optimisation refactoring

The refactoring moves the collection compute (filter, sort, group, piles, clusters, selection)
from the webview to the Rust backend. The front then renders slices of the results instead of
holding every column. These notes cover the design. The port as a whole, with its phases and
rules, is in [`technical_docs/rust_port/PLAN.md`](../technical_docs/rust_port/PLAN.md): these
notes detail its P1-C (engine), P4 (backend compute + view protocol) and P5 (thin client).

| note | content |
|---|---|
| [01-collection-manager.md](01-collection-manager.md) | the backend collection manager: API, performance strategy, implementation plan |
| [02-slice-sending.md](02-slice-sending.md) | tree slices: the UI requests pieces of the resulting tree and builds its own lines; caching, seeking, invalidation, many collections on one backend |
| [03-sqlite-layout.md](03-sqlite-layout.md) | the data.db layout the engine wants: typed values, property-first keys, sha1 ids, what it saves, compatibility |

Measurements behind the numbers quoted here: [`bench/collection`](../bench/collection/README.md)
(compute, memory and wire, 1M synthetic images).

Conventions: one note per subject, numbered in reading order, dated status line at the top.
When the code and a note disagree, fix the note.
