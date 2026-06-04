"""Shared dependency holders for panoptic2 routes."""
from __future__ import annotations

from fastapi import HTTPException

from panoptic.core.panoptic.panoptic import Panoptic
from panoptic.core.project.project import Project
from panoptic.core.server.panoptic_server import PanopticServer

_panoptic: Panoptic | None = None
_server:   PanopticServer | None = None


def set_dependencies(panoptic: Panoptic, server: PanopticServer) -> None:
    global _panoptic, _server
    _panoptic = panoptic
    _server   = server


def get_panoptic() -> Panoptic:
    return _panoptic


def get_server() -> PanopticServer:
    return _server


def get_project(project_id: str) -> Project:
    project = _panoptic.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f'Project {project_id!r} is not loaded')
    return project
