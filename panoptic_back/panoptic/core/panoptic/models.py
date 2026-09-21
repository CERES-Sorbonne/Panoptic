import msgspec


class ProjectState(msgspec.Struct):
    id: str
    path: str
    name: str
    excluded_plugins: list[str]
    loaded: bool
    #: ok | outdated (convertible) | incompatible | missing — see core/project/conversion.py
    status: str = 'ok'
    problem: str | None = None
