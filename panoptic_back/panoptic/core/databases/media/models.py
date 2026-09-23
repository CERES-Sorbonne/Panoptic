from typing import Any, Annotated, Optional

import msgspec
import numpy

from panoptic.core.databases.entity_schema import PrimaryKey


class VectorType(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    source: str
    params: dict

    def __str__(self):
        model = str(self.params.get('model', 'default').replace('/', ''))
        return f"{self.source}_{model}_{self.id}"

    def __hash__(self):
        return hash(str(self))

class Vector(msgspec.Struct, array_like=True):
    type_id: Annotated[int, PrimaryKey]
    sha1: Annotated[str, PrimaryKey]
    data: numpy.ndarray

class ImageType(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    name: str               # purpose label, e.g. 'small', 'large', 'preview'
    format: str             # 'jpeg' | 'webp' | 'png'
    width: Optional[int]    # max width in px; None = no constraint
    height: Optional[int]   # max height in px; None = no constraint
    auto_gen: bool = True   # generate at import time; False = defer to explicit user action

class Image(msgspec.Struct, array_like=True):
    type_id: Annotated[int, PrimaryKey]
    sha1: Annotated[str, PrimaryKey]
    data: bytes

class ImageAtlas(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey] # needed if we want to have optimized atlas for big maps where each atlas covers a space region.
    atlas_nb: int # how many atlas files there are
    width: int # in px
    height: int # in px
    cell_width: int # in px
    cell_height: int # in px
    sha1_mapping: dict[str, tuple[int, int]]

class Map(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    source: str
    name: str
    key: str
    count: int
    data: Optional[Any]


