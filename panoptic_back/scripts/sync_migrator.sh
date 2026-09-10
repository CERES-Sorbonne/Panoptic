#!/usr/bin/env bash
# Re-vendor panoptic/migration/ from the standalone migration-panpoic tool.
#
#   scripts/sync_migrator.sh [UPSTREAM_DIR]
#
# UPSTREAM_DIR (or $MIGRATOR_UPSTREAM_DIR) is the root of the standalone tool,
# i.e. the folder holding `migrator/` and `fixtures/`. Everything else there
# (migrate.py, analysis/, envs/, sandboxes/, reports/, out/, scripts/) is
# deliberately NOT vendored. The test fixtures are, because the vendored suite
# is useless without them; they are excluded from the built wheel/sdist.
#
# After running this, re-apply the two local deltas by hand if they are gone:
#   * tests/ import `panoptic.migration.*`, not `migrator.*`
#   * tests/ resolve FIXTURES from tests/fixtures, and ROOT is panoptic_back/
# then run: python -m unittest discover -s panoptic/migration/tests -t .
set -euo pipefail

UPSTREAM="${1:-${MIGRATOR_UPSTREAM_DIR:-$HOME/migration-panpoic}}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$HERE/panoptic/migration"

[ -d "$UPSTREAM/migrator" ] || { echo "no migrator/ in $UPSTREAM" >&2; exit 1; }

rm -rf "$DEST"
mkdir -p "$DEST/tests/fixtures"
tar cf - -C "$UPSTREAM/migrator" --exclude='__pycache__' . | tar xf - -C "$DEST"
tar cf - -C "$UPSTREAM/fixtures" --exclude='__pycache__' . | tar xf - -C "$DEST/tests/fixtures"
find "$DEST" -name '__pycache__' -type d -prune -exec rm -rf {} +
# stray empty mini/ folders break test_writers' fixture preconditions
find "$DEST/tests/fixtures" -type d -name mini -empty -delete

# refresh the provenance marker
COMMIT="$(git -C "$UPSTREAM" rev-parse HEAD 2>/dev/null || true)"
python3 - "$DEST/__init__.py" "$UPSTREAM/migrator" "${COMMIT}" <<'PY'
import datetime, re, sys
path, upstream, commit = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(path).read()
commit_repr = '"%s"' % commit if commit else "None          # upstream is not a git repository"
new = ('MIGRATOR_UPSTREAM = {\n'
       '    "path": "%s",\n'
       '    "commit": %s,\n'
       '    "synced_at": "%s",\n'
       '}' % (upstream, commit_repr, datetime.date.today().isoformat()))
s, n = re.subn(r'MIGRATOR_UPSTREAM = \{.*?\n\}', new, s, flags=re.S)
if not n:
    s += "\n" + new + "\n"
open(path, "w").write(s)
PY
echo "vendored $UPSTREAM/migrator -> $DEST"
