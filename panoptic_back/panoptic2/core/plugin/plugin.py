"""APlugin — abstract base class for all Panoptic2 plugins."""
from __future__ import annotations

from abc import ABC
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from pydantic import BaseModel

from panoptic2.core.plugin.action_registry import ActionRegistry, build_function_description
from panoptic2.core.plugin.plugin_interface import PluginProjectInterface
from panoptic2.models.action_models import (
    FunctionDescription, PluginBaseParamsDescription, PluginDescription,
)

if TYPE_CHECKING:
    from panoptic2.core.project.project import Project2


class APlugin(ABC):
    def __init__(self, name: str, project: Project2, plugin_path: str):
        self.name        = name
        self._project    = project
        self.project     = PluginProjectInterface(project)
        self.plugin_path = plugin_path
        self.params: Any | None = None

        slug = '_'.join(name.split()).lower()
        self.data_path = Path(project.folder) / 'plugin_data' / slug
        self.data_path.mkdir(parents=True, exist_ok=True)

        self.registered_functions: list[FunctionDescription] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._load_params()
        self._start()

    def _start(self) -> None:
        """Override in subclass for plugin-specific initialisation."""

    # ------------------------------------------------------------------
    # Params  (stored per-project in ProjectDB key-value)
    # ------------------------------------------------------------------

    def _load_params(self) -> None:
        if self.params is None:
            return
        stored = self._project.get_plugin_params(self.name)
        if stored:
            try:
                self.params = self.params.__class__(**{**self.params.dict(), **stored})
            except Exception:
                pass

    def update_params(self, params: Any) -> Any:
        if self.params is not None and isinstance(self.params, BaseModel):
            self.params = self.params.model_copy(update=params if isinstance(params, dict) else params.dict())
        self._project.set_plugin_params(self.name, self.params.dict() if self.params else {})
        return self.params

    # ------------------------------------------------------------------
    # Action registration
    # ------------------------------------------------------------------

    def add_action_easy(self, fn: Callable, hooks: list[str] = None) -> FunctionDescription:
        desc = self._project.action.easy_add(self, fn, hooks)
        self.registered_functions.append(desc)
        return desc

    def add_action(self, fn: Callable, description: FunctionDescription) -> FunctionDescription:
        self._project.action.add(fn, description)
        self.registered_functions.append(description)
        return description

    # ------------------------------------------------------------------
    # Description  (for /plugins_info route)
    # ------------------------------------------------------------------

    def get_description(self) -> PluginDescription:
        return PluginDescription(
            name=self.name,
            description=self.__doc__,
            path=self.plugin_path,
            base_params=self._get_base_params_description(),
            registered_functions=self.registered_functions,
        )

    def _get_base_params_description(self) -> PluginBaseParamsDescription:
        if not self.params:
            return PluginBaseParamsDescription()
        doc = self.params.__doc__ or ''
        description = doc[:doc.index('@')].strip() if '@' in doc else doc.strip() or None
        from panoptic2.core.plugin.action_registry import _build_param_descriptions
        params = _build_param_descriptions(self.params.__class__)
        for p in params:
            p.id = p.name
            p.default_value = getattr(self.params, p.name, None)
        return PluginBaseParamsDescription(description=description, params=params)
