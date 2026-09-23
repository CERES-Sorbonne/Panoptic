"""Run report: a structured record of one migration attempt."""

from __future__ import annotations

import datetime
import json
import os
import platform
import sys

from . import __version__


class Report:
    def __init__(self, source_dir, source_db, target_dir, dry_run):
        self.started = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        self.source_dir = source_dir
        self.source_db = source_db
        self.target_dir = target_dir
        self.dry_run = bool(dry_run)
        self.detection = None
        self.steps = []
        self.warnings = []
        self.errors = []
        self.counts = {}
        self.status = "pending"
        #: set by the CLI to echo each finished stage to stdout as it happens.
        #: A long run (task 4.3 saw 12 s for half a million instances) must not
        #: look hung, and the stage names are the same ones `--dry-run` prints.
        self.on_step = None
        self.label = None

    # -- recording ---------------------------------------------------------
    def step(self, name, detail=""):
        self.steps.append({"name": name, "detail": detail})
        if self.on_step is not None:
            self.on_step(name, detail)

    def warn(self, message):
        self.warnings.append(message)

    def error(self, message):
        self.errors.append(message)

    def set_detection(self, detection):
        self.detection = detection
        for w in detection.warnings:
            self.warn(w)

    # -- output ------------------------------------------------------------
    def to_json(self):
        return {
            "migrator_version": __version__,
            "started": self.started,
            "status": self.status,
            "dry_run": self.dry_run,
            "source": {"dir": self.source_dir, "db": self.source_db},
            "target": {"dir": self.target_dir},
            "detection": self.detection.to_json() if self.detection else None,
            "steps": self.steps,
            "counts": self.counts,
            "warnings": self.warnings,
            "errors": self.errors,
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
            },
        }

    # -- markdown ----------------------------------------------------------
    #: RSS per instance measured on three real projects in task 4.3
    #: (24 MB / 18 inst, 130 MB / 30 541, 598 MB / 512 550): the whole project
    #: is read into the IR before anything is written, so peak memory is linear.
    KB_PER_INSTANCE = 1.2

    def memory_note(self):
        """A one-line honest statement of the one known scale limit."""
        n = (self.counts or {}).get("instances")
        base = ("Peak memory is ~1.2 KB per instance: the whole project is read "
                "into an in-memory IR before any database is written. A project "
                "of a few million images therefore needs several GB of RAM "
                "(~4 M instances ~= 4.5 GB) -- the only known scale limit.")
        if isinstance(n, int) and n > 0:
            return ("%s This run held %s instance(s), i.e. roughly %d MB."
                    % (base, "{:,}".format(n), max(1, int(n * self.KB_PER_INSTANCE / 1024))))
        return base

    def _md_counts(self):
        rows = []
        for key, value in (self.counts or {}).items():
            if isinstance(value, dict):
                inner = ", ".join("%s=%s" % (k, v) for k, v in sorted(value.items())
                                  if not isinstance(v, (dict, list)))
                rows.append((key, inner or "-"))
            elif isinstance(value, list):
                rows.append((key, "%d item(s)" % len(value)))
            else:
                rows.append((key, value))
        return rows

    def to_markdown(self):
        """A human-readable run report -- the per-run artefact of task 5.1.

        The JSON alongside it is the machine-readable form; this is the one a
        user actually reads when a migration says something they did not expect.
        """
        L = ["# Panoptic migration run",
             "",
             "| | |",
             "|---|---|",
             "| status | **%s** |" % self.status,
             "| started | %s |" % self.started,
             "| migrator | %s |" % __version__,
             "| source | `%s` |" % (self.source_db or "-"),
             "| target | `%s` |" % (self.target_dir or "(none)"),
             "| dry run | %s |" % ("yes" if self.dry_run else "no"),
             "| python | %s on %s |" % (sys.version.split()[0], platform.platform()),
             ""]
        d = self.detection
        if d:
            L += ["## Source", "",
                  "- detected shape: **%s** (%s)" % (d.shape, d.note),
                  "- variant hint: %s" % d.variant,
                  "- recorded `db_version` key: %r (cross-check only -- it is "
                  "known to lie)" % (d.facts.recorded_db_version,),
                  ""]
        if self.steps:
            L += ["## Stages", "", "| stage | result |", "|---|---|"]
            L += ["| %s | %s |" % (s["name"], s["detail"] or "-") for s in self.steps]
            L.append("")
        rows = self._md_counts()
        if rows:
            L += ["## Counts", "", "| key | value |", "|---|---|"]
            L += ["| %s | %s |" % (k, v) for k, v in rows]
            L.append("")
        L += ["## Warnings", ""]
        L += (["- %s" % w for w in self.warnings] if self.warnings
              else ["None."])
        L.append("")
        if self.errors:
            L += ["## Errors", ""] + ["- %s" % e for e in self.errors] + [""]
        L += ["## Resource note", "", self.memory_note(), ""]
        return "\n".join(L)

    def write_markdown(self, path):
        path = os.path.abspath(os.path.expanduser(path))
        parent = os.path.dirname(path) or "."
        if not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_markdown())
        return path

    def write(self, path):
        path = os.path.abspath(os.path.expanduser(path))
        parent = os.path.dirname(path) or "."
        if not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_json(), fh, indent=2, sort_keys=False)
            fh.write("\n")
        return path

    def summary_lines(self):
        lines = []
        d = self.detection
        if d:
            lines.append("source shape : %s (%s)" % (d.shape, d.note))
            if d.variant != d.shape:
                lines.append("  variant hint: %s (data-only, not authoritative)" % d.variant)
            lines.append("recorded key : db_version=%r" % (d.facts.recorded_db_version,))
        lines.append("source       : %s" % self.source_db)
        lines.append("target       : %s%s"
                     % (self.target_dir or "(not given)", "  [dry-run, nothing written]" if self.dry_run else ""))
        for w in self.warnings:
            lines.append("warning      : %s" % w)
        for e in self.errors:
            lines.append("error        : %s" % e)
        return lines
