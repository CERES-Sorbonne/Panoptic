#!/bin/sh
# Scroller line layout: the real front code (V8, JSC) vs the same layout in Rust (see rust/src/lines.rs).
#   ./lines.sh 1000000                      every tree, both views
#   ./lines.sh 10000000 --trees=flat,tags   extra args go to every engine
#   NO_JS=1 ./lines.sh 10000000             rust only
set -e
N=${1:-1000000}; [ $# -gt 0 ] && shift
DIR=$(cd "$(dirname "$0")" && pwd)
OUT=$DIR/results/lines; mkdir -p "$OUT"
JSC=/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc

(cd "$DIR/rust" && cargo build --release -q)
node "$DIR/js/build-front-lines.js"
echo "rust ($N)" >&2; "$DIR/rust/target/release/collection-bench" --n=$N --lines "$@" > "$OUT/rust-$N.jsonl"
if [ -z "$NO_JS" ]; then
  echo "v8 ($N)" >&2; (cd "$DIR/js" && node --max-old-space-size=14000 lines.js --n=$N --store=raw "$@") > "$OUT/v8-$N.jsonl"
  if [ -x "$JSC" ]; then
    echo "jsc ($N)" >&2; (cd "$DIR/js" && "$JSC" lines.js -- --n=$N --store=raw "$@") > "$OUT/jsc-$N.jsonl"
  fi
fi
node "$DIR/lines-report.js" "$OUT" $N | tee "$OUT/report-$N.md"
