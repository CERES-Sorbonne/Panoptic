#!/bin/sh
# Wire benchmark: today's full-column stream vs windowed payloads (see rust/src/wire.rs).
#   ./wire.sh 1000000                  every payload
#   ./wire.sh 1000000 --win=100,200,500
# Payloads go to results/wire/<n>/ (large: ~the whole collection as NDJSON), timings to
# results/wire/<impl>-<n>.jsonl.
set -e
N=${1:-1000000}; [ $# -gt 0 ] && shift
DIR=$(cd "$(dirname "$0")" && pwd)
OUT=$DIR/results/wire; PAY=$OUT/$N; mkdir -p "$PAY"
JSC=/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc
PY=$DIR/../../panoptic_back/.venv/bin/python

(cd "$DIR/rust" && cargo build --release -q)
[ -d "$DIR/js/node_modules/msgpackr" ] || (cd "$DIR/js" && npm install --no-audit --no-fund --ignore-scripts -s)
echo "rust ($N)" >&2;  "$DIR/rust/target/release/collection-bench" --n=$N --wire="$PAY" "$@" > "$OUT/rust-$N.jsonl"
if [ -x "$PY" ]; then
  echo "python ($N)" >&2; "$PY" "$DIR/py/stream_encode.py" --dir="$PAY" > "$OUT/python-$N.jsonl"
fi
echo "v8 ($N)" >&2;    (cd "$DIR/js" && node --max-old-space-size=14000 wire.js --dir="$PAY") > "$OUT/v8-$N.jsonl"
if [ -x "$JSC" ]; then
  echo "jsc ($N)" >&2; (cd "$DIR/js" && "$JSC" wire.js -- --dir="$PAY") > "$OUT/jsc-$N.jsonl"
fi
node "$DIR/wire-report.js" "$OUT" $N | tee "$OUT/report-$N.md"
