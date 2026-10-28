#!/bin/sh
# Run the collection benchmark on every engine for one collection size and print the report.
#   ./run.sh 1000000                 all ops
#   ./run.sh 10000000 --skip=text    extra args go to every engine (--only/--skip/--reps/--warmup)
set -e
N=${1:-1000000}; [ $# -gt 0 ] && shift
DIR=$(cd "$(dirname "$0")" && pwd)
OUT=$DIR/results; mkdir -p "$OUT"
NM=$DIR/../../panoptic_front/node_modules
JSC=/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc
NODE="node --expose-gc --max-old-space-size=14000"

(cd "$DIR/rust" && cargo build --release -q)
echo "rust ($N)" >&2;   "$DIR/rust/target/release/collection-bench" --n=$N "$@" > "$OUT/rust-$N.jsonl"
echo "v8 ($N)" >&2;     $NODE "$DIR/js/bench.js" --n=$N --nm="$NM" "$@" > "$OUT/v8-$N.jsonl"
if [ -x "$JSC" ]; then
  echo "jsc ($N)" >&2;  "$JSC" "$DIR/js/bench.js" -- --n=$N --nm="$NM" "$@" > "$OUT/jsc-$N.jsonl"
fi
if [ -z "$NO_RAW" ]; then
  echo "v8-raw ($N)" >&2; $NODE "$DIR/js/bench.js" --n=$N --store=raw "$@" > "$OUT/v8-raw-$N.jsonl"
fi
node "$DIR/report.js" "$OUT" $N
