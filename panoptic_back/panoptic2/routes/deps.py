"""Shared dependency holders for panoptic2 routes."""
from __future__ import annotations

from fastapi import HTTPException

from panoptic2.core.panoptic.panoptic import Panoptic2
from panoptic2.core.project.project import Project2
from panoptic2.core.server.panoptic_server import PanopticServer2

_panoptic: Panoptic2 | None = None
_server:   PanopticServer2 | None = None


def set_dependencies(panoptic: Panoptic2, server: PanopticServer2) -> None:
    global _panoptic, _server
    _panoptic = panoptic
    _server   = server


def get_panoptic() -> Panoptic2:
    return _panoptic


def get_server() -> PanopticServer2:
    return _server


def get_project(project_id: str) -> Project2:
    project = _panoptic.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f'Project {project_id!r} is not loaded')
    return project
