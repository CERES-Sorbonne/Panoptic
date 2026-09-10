"""Conversion stage plumbing.

    read-legacy  ->  write-data-db  ->  write-media-db  ->  write-project-db
                 ->  post-conditions  ->  register-project

`write-project-db` runs *after* the other two: its `id_registry` is seeded from
`MAX(id) + 1` over the rows they actually wrote (ID_STRATEGY 2.2), so it cannot
run before they exist. The stage list below is the execution order, which is
also what `--dry-run` prints.

`register-project` (task 3.4) writes the panoptic home instance DB; it is the
other half of the `projects.id == project_config.id` invariant. It runs only
when a home DB is named (`--register` / `--panoptic-db`), because that file
lives outside the project folder and belongs to the whole panoptic install --
a conversion must not reach into it uninvited. When it is skipped, the report
carries the exact command that finishes the job.
"""

from __future__ import annotations

import os
from collections import namedtuple

from .home import default_home_db
from .readers import read_source
from .schema import checkpoint
from .schema.check import check_upstream
from .source import TARGET_DB_NAMES
from .writers import PostConditions, write_data_db, write_media_db, write_project_db
from .writers.panoptic_db import PanopticHomeWriter

Stage = namedtuple("Stage", "name description task")


class PipelineNotImplemented(Exception):
    """A conversion stage has not been written yet (task 3.4)."""


PIPELINE = (
    Stage("read-legacy",
          "read the source into the common intermediate representation", "3.2"),
    Stage("write-data-db",
          "write data.db (folders, files, instances, properties, tags, values,"
          " and the genesis journal)", "3.3"),
    Stage("write-media-db",
          "write media.db (thumbnails, image_atlas, maps)", "3.3/3.5"),
    Stage("write-project-db",
          "write project.db (id_registry, project_config, user_defaults)", "3.3"),
    Stage("check",
          "assert the post-conditions against the written databases", "3.3"),
    Stage("register-project",
          "register the project in the panoptic home instance DB", "3.4"),
)

#: Everything deliberately NOT carried over, per the signed-off decisions in
#: CLAUDE.md. No flags. This is the *policy*; the per-run counts come from
#: `ir.dropped.summary_lines()` once the source has actually been read, so the
#: report states how much of each was thrown away rather than only that it was.
DROPPED = (
    "tabs and all UI layout data (L3)",
    "vectors (recompute them in the new Panoptic)",
    "raw_images original-file blobs (L6)",
)


def run_pipeline(detection, source_db, target_dir, report, home_db=None):
    for warning in check_upstream():
        report.warn(warning)

    source_dir = os.path.dirname(os.path.abspath(source_db))

    # -- 3.2 ---------------------------------------------------------------
    ir = read_source(detection, source_db, project_dir=source_dir)
    report.step("read-legacy", ir.summary())
    report.counts.update(ir.counts())
    report.counts["dropped"] = ir.dropped.to_json()
    report.counts["max_ids"] = ir.max_ids()
    for line in ir.dropped.summary_lines():
        report.warn(line)
    for w in ir.warnings:
        report.warn(w)
    for w in _mini_folder_warning(source_dir):
        report.warn(w)

    os.makedirs(target_dir, exist_ok=True)
    project_path, data_path, media_path = [
        os.path.join(target_dir, name) for name in TARGET_DB_NAMES]

    # -- 3.3: data.db ------------------------------------------------------
    data_writer, data_stats = write_data_db(data_path, ir, report)
    report.step("write-data-db", _fmt(data_stats))
    report.counts["data_db"] = data_stats
    _report_skips(report, "data.db", data_writer.skipped)

    # -- 3.3: media.db -----------------------------------------------------
    media_writer, media_stats = write_media_db(
        media_path, ir, source_dir=source_dir, target_dir=target_dir,
        report=report)
    report.step("write-media-db", _fmt(media_stats))
    report.counts["media_db"] = media_stats
    _report_skips(report, "media.db", media_writer.skipped)

    # -- 3.3: project.db (last: its counters come from the output) ---------
    project_writer, project_stats = write_project_db(
        project_path, ir, data_path, media_path,
        name=os.path.basename(os.path.abspath(target_dir)),
        system=data_writer.system, report=report)
    report.step("write-project-db", _fmt(project_stats.get("id_registry", {})))
    report.counts["project_db"] = project_stats
    report.counts["project_id"] = project_writer.project_id
    for note in project_writer.notes:
        report.warn(note)

    # -- 3.3: post-conditions ---------------------------------------------
    checks = PostConditions(project_path, data_path, media_path).assert_ok()
    report.step("check", "%d post-conditions passed" % len(checks))
    report.counts["post_conditions"] = len(checks)

    for path in (data_path, media_path, project_path):
        checkpoint(path)

    # -- 3.4 ---------------------------------------------------------------
    register_project(target_dir, project_writer.project_id, home_db, report)
    return ir


def register_project(target_dir, project_id, home_db, report):
    """Write the panoptic-home half of `projects.id == project_config.id`.

    With no `home_db` nothing outside the project folder is touched; the step
    still records the id and the one command that registers it, so the folder is
    never left in an unexplained half-registered state.
    """
    if not home_db:
        report.counts["registered"] = False
        report.step("register-project",
                    "skipped: no panoptic home DB given (--register)")
        report.warn(
            "the project folder is written but not registered: run "
            "`python3 migrate.py register %s` to add it to the panoptic home "
            "DB (%s), or re-run with --register. `projects.id` there must be "
            "%s, the project_config.id written here."
            % (_q(target_dir), default_home_db(), project_id))
        return None

    with PanopticHomeWriter(home_db, report=report) as writer:
        action = writer.register_project(project_id, target_dir,
                                         name=os.path.basename(
                                             os.path.abspath(target_dir)))
        for note in writer.notes:
            report.warn("panoptic home: %s" % note)
        created = writer.created
        instance_id = writer.instance_id
    report.counts["registered"] = {
        "panoptic_db": os.path.abspath(os.path.expanduser(home_db)),
        "created": created, "action": action,
        "instance_id": instance_id, "project_id": project_id,
    }
    report.step("register-project",
                "%s in %s (instance %s)%s"
                % (action, home_db, instance_id,
                   " [new home DB created]" if created else ""))
    return home_db


def _mini_folder_warning(source_dir):
    """0.3.3/0.3.4 (shapes v1/v2) kept thumbnails as `<project>/mini/<sha1>.jpeg`.

    Nothing reads that folder -- the thumbnails there are dropped, and the new
    Panoptic only generates thumbnails on import, never on open, so those
    projects browse at full resolution until they are resynced. Cosmetic, but
    permanent and invisible, so the run report says it out loud (task 4.2).
    """
    mini = os.path.join(source_dir, "mini")
    try:
        n = len([f for f in os.listdir(mini) if f.lower().endswith(
            (".jpeg", ".jpg", ".png"))])
    except OSError:
        return []
    if not n:
        return []
    return ["%d on-disk thumbnail(s) in %s are NOT carried over (0.3.x kept "
            "them there instead of in the database). The new Panoptic only "
            "generates thumbnails on import, so this project will browse at "
            "full resolution until the folder is resynced. Images themselves "
            "are unaffected." % (n, mini)]


def _q(path):
    return '"%s"' % path if " " in str(path) else path


def _fmt(stats):
    return ", ".join("%s=%s" % (k, v) for k, v in sorted(stats.items())
                     if not isinstance(v, dict))


def _report_skips(report, where, skipped):
    for reason, n in sorted(skipped.items()):
        report.warn("%s: skipped %d row(s): %s" % (where, n, reason))
