from enum import Enum
from typing import TypeAlias

from pydantic import BaseModel


class Plugin(BaseModel):
    name: str
    object: str
    description: str
    import_image:
    cluster:
    similarity:
    run:

DataType:TypeAlias = "str" | int | "date" | "vector"

class ActionReturns(BaseModel):

class ActionInputs(BaseModel):
    name: str
    data_type: DataType | list[DataType]
    prop: bool # should result be stored in panoptic db as a prop ?

class Action(BaseModel):
    description: str
    inputs: list[ActionInputs]
    returns: list[ActionReturns]


class PanopticInputs(Enum):
    vectors = "vectors"
    paths = "paths"
    ids = "ids"