"""Command line entry point: `python -m migrator <old_project> <new_project>`."""

from __future__ import annotations

import argparse
import datetime
import os
import re
import sys

from . import __version__
from .detect import detect_db
from .errors import MigratorError, UnknownShape
from .home import (default_home_db, detect_home, discover_homes,
                   legacy_home_dir, migrate_home, usable_homes)
from .pipeline import PIPELINE, PipelineNotImplemented, run_pipeline
from .report import Report
from .source import assert_distinct, check_target, resolve_source
from .writers.panoptic_db import PanopticHomeWriter, read_project_config

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2          # argparse's own code
EXIT_UNKNOWN_SHAPE = 3
EXIT_NOT_IMPLEMENTED = 4

#: This file lives in `<root>/migrator/`; run reports go to `<root>/reports/`,
#: next to the ones the build tasks wrote, so a hand-run always leaves a trail
#: in one predictable place. `$MIGRATOR_REPORT_DIR` overrides it (the test
#: suite points it at a temp dir; a read-only install needs it too).
PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_report_dir():
    return os.path.abspath(os.path.expanduser(
        os.environ.get("MIGRATOR_REPORT_DIR")
        or os.path.join(PACKAGE_ROOT, "reports")))


def _prog(sub=""):
    """The command line the user actually typed, for usage strings."""
    base = os.path.basename(sys.argv[0] or "")
    prog = "python3 migrate.py" if base == "migrate.py" else "python3 -m migrator"
    return prog + (" " + sub if sub else "")


def _slug(text):
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(str(text or "")))
    return slug.strip("-") or "run"


def run_report_paths(kind, label):
    """`(markdown, json)` under the report dir, stamped so runs never collide."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(default_report_dir(),
                        "%s-%s-%s" % (stamp, kind, _slug(label)))
    return base + ".md", base + ".json"


def write_run_report(report, kind, label, out, explicit=None, enabled=True):
    """Write the per-run report (markdown + JSON) and say where it went.

    `explicit` is the user's `--report PATH`: it names the JSON, and the
    markdown lands beside it. With no `--report`, both go to the report dir.
    Failure to write a report never fails a migration that already succeeded --
    it is reported on stderr and the exit code stands.
    """
    if not enabled:
        return None
    if explicit:
        json_path = os.path.abspath(os.path.expanduser(explicit))
        md_path = os.path.splitext(json_path)[0] + ".md"
    else:
        md_path, json_path = run_report_paths(kind, label)
    try:
        report.write(json_path)
        report.write_markdown(md_path)
    except OSError as exc:
        print("warning: could not write the run report: %s" % exc,
              file=sys.stderr)
        return None
    out("report       : %s" % md_path)
    out("               %s" % json_path)
    return md_path

DESCRIPTION = """\
Convert a Panoptic project made by any released 0.x version into the new
multi-database format (project.db + data.db + media.db).

The source project is opened strictly read-only and is never modified.
The source schema shape is detected by sniffing sqlite_master -- the recorded
`db_version` key is a cross-check only, because it is known to lie.

Three further subcommands handle the panoptic *home* registry, which lives
outside any project folder:

  discover      list every legacy registry on this machine (there is often
                more than one: panoptic.db and panoptic-dev.db side by side)
  migrate-home  convert the legacy global registry (<datadir>/panoptic/
                panoptic.db or projects.json) into a new-format panoptic.db
  register      add an already-migrated project folder to a panoptic home DB

None of them ever rewrites a legacy registry in place: the legacy home and the
new home (~/.panoptic/panoptic.db) are different files, and --out is required.

Every run writes a report (markdown + JSON) under the migrator's own reports/
folder unless --no-report is given.
"""


def build_parser():
    p = argparse.ArgumentParser(
        prog=_prog(),
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("old_project_dir",
                   help="legacy project folder (or its panoptic.db directly)")
    p.add_argument("new_project_dir", nargs="?",
                   help="destination folder; must not exist or must be empty. "
                        "Optional with --dry-run.")
    p.add_argument("--dry-run", action="store_true",
                   help="detect and plan only; write nothing")
    p.add_argument("--register", action="store_true",
                   help="also register the migrated folder in the panoptic "
                        "home DB (default: %s)" % default_home_db())
    p.add_argument("--panoptic-db", metavar="PATH",
                   help="the panoptic home DB to register into; implies "
                        "--register. Created if it does not exist.")
    p.add_argument("--report", metavar="PATH",
                   help="write the run report to PATH (.json; the .md lands "
                        "beside it). Default: a timestamped pair in %s"
                        % default_report_dir())
    p.add_argument("--no-report", action="store_true",
                   help="do not write a run report at all")
    p.add_argument("-q", "--quiet", action="store_true",
                   help="print nothing but errors; warnings are still "
                        "recorded in the run report")
    p.add_argument("--version", action="version",
                   version="panoptic migrator %s" % __version__)
    return p


SUBCOMMANDS = ("migrate-home", "register", "discover")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in SUBCOMMANDS:
        name = argv.pop(0)
        if name == "migrate-home":
            return main_migrate_home(argv)
        if name == "discover":
            return main_discover(argv)
        return main_register(argv)
    return main_project(argv)


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------

def main_discover(argv):
    """List *every* legacy panoptic home on this machine, and classify each.

    Its own subcommand because "which registries exist here?" is a question the
    user has to be able to ask before deciding what to migrate -- and because
    the answer is routinely more than one file (see `home.legacy_home_candidates`).
    """
    p = argparse.ArgumentParser(
        prog=_prog("discover"),
        description="List the legacy panoptic home registries found on this "
                    "machine. Read-only: nothing is opened for writing.")
    p.add_argument("--dir", metavar="PATH", default=None,
                   help="look here instead of %s" % legacy_home_dir())
    args = p.parse_args(argv)

    base = args.dir or str(legacy_home_dir())
    found = discover_homes(base)
    print("panoptic migrator %s" % __version__)
    print("looking in   : %s" % base)
    print("new home     : %s" % default_home_db())
    print("")
    if not found:
        print("no legacy panoptic home found.")
        print("A legacy home is <datadir>/panoptic/panoptic.db (0.7.x) or "
              "projects.json (<= 0.6.8).")
        return EXIT_ERROR
    for d in found:
        print("  %s" % d.path)
        if d.problem:
            print("      shape    : %s" % (d.shape or "unreadable"))
            print("      UNUSABLE : %s" % d.problem)
        else:
            print("      shape    : %s" % d.shape)
            print("      contents : %d project(s), %d plugin(s)"
                  % (d.projects, d.plugins))
    usable = usable_homes(found)
    print("")
    print("%d registry/registries found, %d usable."
          % (len(found), len(usable)))
    if len(usable) > 1:
        print("More than one legacy registry holds projects, and they usually "
              "hold DIFFERENT ones -- migrate every one of them, or you will "
              "silently lose the projects recorded only in the others:")
        for d in usable:
            print("  python3 migrate.py migrate-home %s --out <new panoptic.db>"
                  % _quote(d.path))
        print("  (or pass --all once to do them all into a single --out)")
    return EXIT_OK


def _quote(path):
    return '"%s"' % path if " " in path else path


# ---------------------------------------------------------------------------
# migrate-home
# ---------------------------------------------------------------------------

HOME_DESCRIPTION = """\
Convert the legacy panoptic *home* registry into the new panoptic.db.

Legacy home:  <datadir>/panoptic/panoptic.db   (0.7.x)
              <datadir>/panoptic/projects.json (<= 0.6.x)
New home:     $PANOPTIC_DB, default ~/.panoptic/panoptic.db

The source is opened read-only and never rewritten; --out names the new file.

A legacy project is registered only when a *migrated* folder for it can be
found, because `projects.id` must equal that folder's `project_config.id` --
inventing one would make `load_project` refuse the folder. Point at the
migrated folders with `--map <legacy path>=<migrated folder>` (repeatable).
Anything unresolved is listed as skipped rather than guessed at.
"""


def build_home_parser():
    p = argparse.ArgumentParser(
        prog=_prog("migrate-home"),
        description=HOME_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", nargs="?",
                   help="legacy panoptic.db or projects.json. With none, the "
                        "platform data dir is searched; if it holds more than "
                        "one registry the run stops and lists them, because "
                        "picking one silently would drop the others' projects "
                        "(use --all to take them all).")
    p.add_argument("--out", metavar="PATH", required=True,
                   help="the new panoptic.db to write (created if missing, "
                        "upserted into if it already exists)")
    p.add_argument("--map", metavar="OLD=NEW", action="append", default=[],
                   help="legacy project path = its migrated folder; repeatable")
    p.add_argument("--all", action="store_true", dest="all_homes",
                   help="migrate every legacy registry found on this machine "
                        "into the one --out file, instead of refusing to "
                        "choose between them")
    p.add_argument("--report", metavar="PATH",
                   help="write the run report to PATH (.json; the .md lands "
                        "beside it). Default: a timestamped pair in %s"
                        % default_report_dir())
    p.add_argument("--no-report", action="store_true")
    p.add_argument("-q", "--quiet", action="store_true")
    return p


def resolve_home_sources(args, out):
    """The registries this invocation should read, or `(None, exit code)`.

    The rule task 4.3 asked for: **never silently pick one**. An explicit
    `source` wins. Otherwise every registry on the machine is listed, and a
    single usable one is used; several are an error unless `--all` says the
    user meant all of them.
    """
    if args.source:
        return [os.path.abspath(os.path.expanduser(args.source))], None

    found = discover_homes()
    if not found:
        print("error: no legacy panoptic home found under %s. Pass one "
              "explicitly." % legacy_home_dir(), file=sys.stderr)
        return None, EXIT_ERROR

    out("registries found in %s:" % legacy_home_dir())
    for d in found:
        if d.problem:
            out("  %s  [%s] UNUSABLE: %s" % (d.path, d.shape or "?", d.problem))
        else:
            out("  %s  [%s] %d project(s), %d plugin(s)"
                % (d.path, d.shape, d.projects, d.plugins))
    out("")

    usable = usable_homes(found)
    if not usable:
        print("error: %d registry/registries found under %s but none is a "
              "readable legacy home (see the list above)."
              % (len(found), legacy_home_dir()), file=sys.stderr)
        return None, EXIT_ERROR
    if len(usable) == 1 or args.all_homes:
        return [d.path for d in usable], None

    print("error: %d legacy registries were found and they hold different "
          "project sets; refusing to guess which one you meant.\n"
          "Pass one explicitly, or --all to migrate every one of them into "
          "the same --out:\n  %s"
          % (len(usable), "\n  ".join(d.path for d in usable)),
          file=sys.stderr)
    return None, EXIT_USAGE


def main_migrate_home(argv):
    args = build_home_parser().parse_args(argv)
    out = (lambda *a: None) if args.quiet else (lambda *a: print(*a))

    out("panoptic migrator %s" % __version__)
    sources, rc = resolve_home_sources(args, out)
    if sources is None:
        return rc
    if len(sources) > 1:
        out("migrating %d registries into one home: %s"
            % (len(sources), args.out))
    # with several sources a single --report path would have each run clobber
    # the last; fall back to the timestamped default in that case.
    args.explicit_report = args.report if len(sources) == 1 else None
    rc = EXIT_OK
    for source in sources:
        one = _migrate_one_home(args, source, out)
        rc = one if one != EXIT_OK else rc
    return rc


def _migrate_one_home(args, source, out):
    mapping = {}
    for entry in args.map:
        if "=" not in entry:
            print("error: --map expects OLD=NEW, got %r" % entry, file=sys.stderr)
            return EXIT_USAGE
        old, new = entry.split("=", 1)
        mapping[old] = new

    report = Report(os.path.dirname(source), source, None, False)
    report.on_step = None if args.quiet else (
        lambda name, detail: print("  [%s] %s" % (name, detail)))
    try:
        shape = detect_home(source)
        out("")
        out("legacy home  : %s (%s)" % (source, shape))
        out("target home  : %s" % os.path.abspath(os.path.expanduser(args.out)))

        result = migrate_home(source, args.out, mapping, report)
        report.status = "ok"
        report.counts["home"] = result.to_json()
        report.step("migrate-home", result.summary())

        out("")
        for legacy_id, new_id, path in result.registered:
            out("  registered   %-3s -> %s  %s" % (legacy_id, new_id, path))
        for legacy_id, path, reason in result.skipped:
            out("  SKIPPED      %-3s     %s" % (legacy_id, path))
            out("               %s" % reason)
        for name in result.plugins:
            out("  plugin       %s" % name)
        out("")
        out("done: %s" % result.summary())
        if result.skipped:
            out("hint: migrate those project folders first, then re-run with "
                "--map <legacy path>=<migrated folder>.")
        rc = EXIT_OK
    except UnknownShape as exc:
        print("error: %s" % exc, file=sys.stderr)
        report.status = "refused"
        report.error(str(exc))
        rc = EXIT_UNKNOWN_SHAPE
    except MigratorError as exc:
        print("error: %s" % exc, file=sys.stderr)
        report.status = "failed"
        report.error(str(exc))
        rc = EXIT_ERROR

    write_run_report(report, "migrate-home", os.path.basename(source), out,
                     explicit=getattr(args, "explicit_report", args.report),
                     enabled=not args.no_report)
    return rc


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------

def build_register_parser():
    p = argparse.ArgumentParser(
        prog=_prog("register"),
        description="Register an already-migrated project folder in a panoptic "
                    "home DB. The id is read from the folder's project.db, "
                    "never invented -- `load_project` compares the two.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("project_dir", help="a migrated folder (containing project.db)")
    p.add_argument("--panoptic-db", metavar="PATH", default=None,
                   help="home DB to write (default: %s)" % default_home_db())
    p.add_argument("--name", help="override the registered project name")
    p.add_argument("--report", metavar="PATH")
    p.add_argument("--no-report", action="store_true")
    p.add_argument("-q", "--quiet", action="store_true")
    return p


def main_register(argv):
    args = build_register_parser().parse_args(argv)
    out = (lambda *a: None) if args.quiet else (lambda *a: print(*a))
    home_db = args.panoptic_db or default_home_db()
    folder = os.path.abspath(os.path.expanduser(args.project_dir))

    report = Report(folder, os.path.join(folder, "project.db"), None, False)
    try:
        project_id, config_name, _ = read_project_config(folder)
        with PanopticHomeWriter(home_db, report=report) as writer:
            action = writer.register_project(
                project_id, folder,
                name=args.name or config_name or os.path.basename(folder))
            notes, created, instance_id = (writer.notes, writer.created,
                                           writer.instance_id)
        for note in notes:
            report.warn(note)
            out("note         : %s" % note)
        report.status = "ok"
        report.counts["registered"] = {
            "panoptic_db": os.path.abspath(os.path.expanduser(home_db)),
            "created": created, "action": action,
            "instance_id": instance_id, "project_id": project_id}
        report.step("register", "%s %s" % (action, project_id))
        out("panoptic migrator %s" % __version__)
        out("project      : %s" % folder)
        out("project id   : %s" % project_id)
        out("panoptic home: %s%s" % (home_db,
                                     "  [created]" if created else ""))
        out("%s." % action)
        rc = EXIT_OK
    except MigratorError as exc:
        print("error: %s" % exc, file=sys.stderr)
        report.status = "failed"
        report.error(str(exc))
        rc = EXIT_ERROR

    write_run_report(report, "register", os.path.basename(folder), out,
                     explicit=args.report, enabled=not args.no_report)
    return rc


# ---------------------------------------------------------------------------
# the project conversion (the default, argument-compatible entry point)
# ---------------------------------------------------------------------------

def main_project(argv):
    args = build_parser().parse_args(argv)
    out = (lambda *a: None) if args.quiet else (lambda *a: print(*a))

    if args.new_project_dir is None and not args.dry_run:
        print("error: new_project_dir is required unless --dry-run is given",
              file=sys.stderr)
        return EXIT_USAGE

    report = None
    try:
        source_dir, source_db = resolve_source(args.old_project_dir)
        target_dir = None
        if args.new_project_dir is not None:
            target_dir = check_target(args.new_project_dir, dry_run=args.dry_run)
            assert_distinct(source_dir, target_dir)

        report = Report(source_dir, source_db, target_dir, args.dry_run)
        detection = detect_db(source_db)
        report.set_detection(detection)

        out("panoptic migrator %s" % __version__)
        for line in report.summary_lines():
            out(line)

        out("")
        out("plan:")
        for stage in PIPELINE:
            out("  %-28s %s" % (stage.name, stage.description))
        # Progress: the pipeline is a fixed six-stage sequence, so echoing each
        # stage as it completes is the whole progress story. `read-legacy` is
        # the long pole (12 s for 512 550 instances in task 4.3), so announce it
        # before it starts rather than only when it is over.
        report.on_step = None if args.quiet else (
            lambda name, detail: print("  [%d/%d] %-18s %s"
                                       % (_stage_no(name), len(PIPELINE),
                                          name, detail)))

        if args.dry_run:
            report.status = "dry-run"
            for stage in PIPELINE:
                report.step(stage.name, "planned (dry-run)")
            out("")
            out("dry run: nothing written.")
            rc = EXIT_OK
        else:
            home_db = args.panoptic_db or (
                default_home_db() if args.register else None)
            # Everything after this point is new: `summary_lines()` was printed
            # before the run, so only the warnings the run itself produced --
            # the per-run drop counts included -- are still unseen.
            seen = len(report.warnings)
            out("")
            out("running (this can take a while on a large project; peak "
                "memory is ~1.2 KB per instance):")
            run_pipeline(detection, source_db, target_dir, report,
                         home_db=home_db)
            report.status = "ok"
            out("")
            for line in report.warnings[seen:]:
                out("warning      : %s" % line)
            out("")
            out("done -> %s" % target_dir)
            out("note         : %s" % report.memory_note())
            rc = EXIT_OK

    except UnknownShape as exc:
        msg = "unrecognised source schema: %s" % exc
        print("error: %s" % msg, file=sys.stderr)
        print("hint: this migrator supports panoptic project databases from "
              "0.0.1 through 0.7.6 only.", file=sys.stderr)
        if report is not None:
            report.status = "refused"
            report.error(msg)
        rc = EXIT_UNKNOWN_SHAPE
    except PipelineNotImplemented as exc:
        print("error: %s" % exc, file=sys.stderr)
        if report is not None:
            report.status = "incomplete"
            report.error(str(exc))
        rc = EXIT_NOT_IMPLEMENTED
    except MigratorError as exc:
        print("error: %s" % exc, file=sys.stderr)
        if report is not None:
            report.status = "failed"
            report.error(str(exc))
        rc = EXIT_ERROR

    if report is not None:
        write_run_report(report, "migrate",
                         os.path.basename(report.target_dir
                                          or report.source_dir or "project"),
                         out, explicit=args.report,
                         enabled=not args.no_report)
    return rc


def _stage_no(name):
    for i, stage in enumerate(PIPELINE, 1):
        if stage.name == name:
            return i
    return 0
