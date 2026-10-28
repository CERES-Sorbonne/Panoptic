#!/bin/sh
# Column load benchmark: a full property column from data.db into the Rust engine's store vs
# through today's Python route (+ the front's ingest of that route's bytes).
#   ./load.sh 1000000               every column
#   ./load.sh 1000000 --only=tags   extra args go to the Rust and Python runs
# data.db is built once per N in results/load/<n>/ (large, gitignored), timings go to
# results/load/<impl>-<n>.jsonl and the report to results/load/report-<n>.md.
set -e
N=${1:-1000000}; [ $# -gt 0 ] && shift
DIR=$(cd "$(dirname "$0")" && pwd)
OUT=$DIR/results/load; PAY=$OUT/$N; DB=$PAY/data.db; mkdir -p "$PAY"
JSC=/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc
BACK=$DIR/../../panoptic_back
PY="$BACK/.venv/bin/python"

(cd "$DIR/load" && cargo build --release -q)
BIN=$DIR/load/target/release/load-bench
if [ ! -f "$DB" ]; then
  echo "data.db ($N)" >&2
  (cd "$BACK" && "$PY" "$DIR/py/column_load.py" --create="$DB")
  "$BIN" --make-db="$DB" --n=$N
fi
echo "rust ($N)" >&2;   "$BIN" --db="$DB" "$@" > "$OUT/rust-$N.jsonl"
echo "python ($N)" >&2; (cd "$BACK" && "$PY" "$DIR/py/column_load.py" --db="$DB" --dump="$PAY" "$@") > "$OUT/python-$N.jsonl"
[ -d "$DIR/js/node_modules/msgpackr" ] || (cd "$DIR/js" && npm install --no-audit --no-fund --ignore-scripts -s)
if [ -x "$JSC" ]; then
  echo "jsc ingest ($N)" >&2; (cd "$DIR/js" && "$JSC" wire.js -- --dir="$PAY") > "$OUT/jsc-$N.jsonl"
fi
node "$DIR/load-report.js" "$OUT" $N | tee "$OUT/report-$N.md"
