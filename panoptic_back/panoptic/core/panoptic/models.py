import msgspec


class ProjectState(msgspec.Struct):
    id: str
    path: str
    name: str
    excluded_plugins: list[str]
    loaded: bool
