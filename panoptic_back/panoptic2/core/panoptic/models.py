import msgspec

from panoptic.core.databases.panoptic.models import PluginKey, ProjectKey, User


class PanopticState(msgspec.Struct):
    projects:           list[ProjectKey]
    loaded_project_ids: list[str]
    plugins:            list[PluginKey]
    users:              list[User]
