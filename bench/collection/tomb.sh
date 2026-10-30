#!/bin/sh
# Delete bookkeeping benchmark: inline tombstones (today, and lean), a tombstone table, or
# no tombstones (full column reload). See load/src/bin/tomb.rs.
#   ./tomb.sh 1000000            all variants x dead fractions
#   DEAD="0 0.1" ./tomb.sh 100000
# Scratch dbs go to results/tomb/db (deleted after each case), timings to
# results/tomb/tomb-<n>.jsonl and the report to results/tomb/report-<n>.md.
set -e
N=${1:-1000000}
DIR=$(cd "$(dirname "$0")" && pwd)
OUT=$DIR/results/tomb; mkdir -p "$OUT/db"
(cd "$DIR/load" && cargo build --release -q --bin tomb)
: > "$OUT/tomb-$N.jsonl"
for dead in ${DEAD:-0 0.01 0.1 0.5}; do
  for v in inline lean table full; do
    echo "$v dead=$dead ($N)" >&2
    "$DIR/load/target/release/tomb" --n=$N --dead=$dead --variant=$v --dir="$OUT/db" >> "$OUT/tomb-$N.jsonl"
  done
done
rmdir "$OUT/db" 2>/dev/null || true
node "$DIR/tomb-report.js" "$OUT" $N | tee "$OUT/report-$N.md"
