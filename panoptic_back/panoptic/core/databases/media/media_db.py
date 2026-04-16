from typing import Union, Iterable

from panoptic.core.databases.media.create import (
    VECTOR_TYPE_SHEMA, VECTOR_SHEMA, IMAGE_TYPE_SHEMA,
    IMAGE_SHEMA, IMAGE_ATLAS_SHEMA, MAP_SHEMA
)
from panoptic.core.databases.media.models import VectorType, Vector, ImageType, Image, ImageAtlas, Map
from panoptic.core.databases.sqlite_db import SQLiteWriter


class MediaDB(SQLiteWriter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_vector_types(self, **filters) -> list[VectorType]:
        return VECTOR_TYPE_SHEMA.get(self.conn, **filters)

    def get_vectors(self, **filters) -> list[Vector]:
        return VECTOR_SHEMA.get(self.conn, **filters)

    def get_image_types(self, **filters) -> list[ImageType]:
        return IMAGE_TYPE_SHEMA.get(self.conn, **filters)

    def get_images(self, **filters) -> list[Image]:
        return IMAGE_SHEMA.get(self.conn, **filters)

    def get_image_atlases(self, **filters) -> list[ImageAtlas]:
        return IMAGE_ATLAS_SHEMA.get(self.conn, **filters)

    def get_maps(self, **filters) -> list[Map]:
        return MAP_SHEMA.get(self.conn, **filters)

    def set_vector_types(self, items: Union[VectorType, Iterable[VectorType]]) -> None:
        VECTOR_TYPE_SHEMA.upsert(self.conn, items)
        self.conn.commit()

    def set_vectors(self, items: Union[Vector, Iterable[Vector]]) -> None:
        VECTOR_SHEMA.upsert(self.conn, items)
        self.conn.commit()

    def set_image_types(self, items: Union[ImageType, Iterable[ImageType]]) -> None:
        IMAGE_TYPE_SHEMA.upsert(self.conn, items)
        self.conn.commit()

    def set_images(self, items: Union[Image, Iterable[Image]]) -> None:
        IMAGE_SHEMA.upsert(self.conn, items)
        self.conn.commit()

    def set_image_atlases(self, items: Union[ImageAtlas, Iterable[ImageAtlas]]) -> None:
        IMAGE_ATLAS_SHEMA.upsert(self.conn, items)
        self.conn.commit()

    def set_maps(self, items: Union[Map, Iterable[Map]]) -> None:
        MAP_SHEMA.upsert(self.conn, items)
        self.conn.commit()