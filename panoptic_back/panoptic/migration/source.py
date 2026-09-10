"""Locating and guarding the source project, and preparing the target folder.

Hard rule (CLAUDE.md): the source is NEVER mutated. Nothing in the migrator
opens the source except through `detect.open_readonly`.
"""

from __future__ import annotations

import os

from .errors import SourceNotFound, TargetExists

LEGACY_DB_NAME = "panoptic.db"
#: filenames the new multi-database format expects, flat in the project folder
#: (analysis/TARGET_NOTES.md section 1). `panoptic.db` is the *instance* DB and
#: lives in the panoptic home, not here.
TARGET_DB_NAMES = ("project.db", "data.db", "media.db")


def resolve_source(path):
    """Accept either a legacy project folder or its panoptic.db directly."""
    path = os.path.abspath(os.path.expanduser(path))
    if os.path.isdir(path):
        db = os.path.join(path, LEGACY_DB_NAME)
        if not os.path.isfile(db):
            raise SourceNotFound(
                "%s contains no %s -- that file is what makes a folder a legacy "
                "panoptic project." % (path, LEGACY_DB_NAME)
            )
        return path, db
    if os.path.isfile(path):
        return os.path.dirname(path), path
    raise SourceNotFound("no such file or directory: %s" % path)


def check_target(path, dry_run=False):
    """Validate the destination folder. Returns its absolute path.

    Refuses a non-empty existing folder so a run can never half-overwrite an
    earlier result; a fresh run must always be reproducible from the source.
    """
    path = os.path.abspath(os.path.expanduser(path))
    if os.path.exists(path):
        if not os.path.isdir(path):
            raise TargetExists("%s exists and is not a directory" % path)
        if os.listdir(path):
            raise TargetExists(
                "%s already exists and is not empty -- refusing to write into "
                "it. Remove it or choose another path." % path
            )
    elif not dry_run:
        parent = os.path.dirname(path) or "."
        if not os.path.isdir(parent):
            raise TargetExists("parent directory does not exist: %s" % parent)
    return path


def assert_distinct(source_dir, target_dir):
    if os.path.realpath(source_dir) == os.path.realpath(target_dir):
        raise TargetExists(
            "the target folder is the source folder -- the source must never be "
            "written to. Choose a different destination."
        )
