"""Test package.

Runs are report-writing by default (task 5.1): every `cli.main()` call would
otherwise drop a timestamped pair of files into the repo's `reports/` folder.
Point the report directory at a throwaway temp dir for the whole suite before
any test module imports `migrator.cli` -- importing this package is what
`unittest discover` does first, so this is the one place that is guaranteed to
run early enough.
"""

import os
import tempfile

os.environ.setdefault(
    "MIGRATOR_REPORT_DIR",
    os.path.join(tempfile.gettempdir(), "migrator-test-reports"))
