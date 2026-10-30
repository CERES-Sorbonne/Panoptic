#!/bin/sh
# Cold-start column load benchmark: value rows vs a cached column blob, on files with none of
# their pages in the OS cache. See load/src/cache.rs.
#   ./cache.sh 1000000
#   ./cache.sh 1000000 --only=tags --reps=3   extra args go to the Rust run
# data.db is shared with load.sh (results/load/<n>/), cache.db and the cold copies go to
# results/cache/<n>/ (large, gitignored), timings to results/cache/cache-<n>.jsonl and the
# report to results/cache/report-<n>.md.
set -e
N=${1:-1000000}; [ $# -gt 0 ] && shift
DIR=$(cd "$(dirname "$0")" && pwd)
DB=$DIR/results/load/$N/data.db
OUT=$DIR/results/cache; mkdir -p "$OUT/$N" "$(dirname "$DB")"
BACK=$DIR/../../panoptic_back
PY="$BACK/.venv/bin/python"

(cd "$DIR/load" && cargo build --release -q)
BIN=$DIR/load/target/release/load-bench
if [ ! -f "$DB" ]; then
  echo "data.db ($N)" >&2
  (cd "$BACK" && "$PY" "$DIR/py/column_load.py" --create="$DB")
  "$BIN" --make-db="$DB" --n=$N
fi
"$BIN" --db="$DB" --cold="$OUT/$N" "$@" > "$OUT/cache-$N.jsonl"
node "$DIR/cache-report.js" "$OUT" $N | tee "$OUT/report-$N.md"
