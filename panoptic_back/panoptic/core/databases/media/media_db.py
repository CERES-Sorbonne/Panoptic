from panoptic.core.databases.media.create import (
    VECTOR_TYPE_SHEMA, VECTOR_SHEMA, IMAGE_TYPE_SHEMA,
    IMAGE_SHEMA, IMAGE_ATLAS_SHEMA, MAP_SHEMA
)
from panoptic.core.databases.media.models import VectorType, Vector, ImageType, Image, ImageAtlas, Map
from panoptic.core.databases.sqlite_db import SQLiteWriter

# Default image types seeded on first open.
# IDs 1 and 2 are reserved; ProjectDB.allocate_image_types() starts at 1 so
# custom types added via the UI will receive IDs 3+ after the defaults are in place.
_DEFAULT_IMAGE_TYPES = [
    ImageType(id=1, name='small', format='jpeg', width=256,  height=256,  auto_gen=True),
    ImageType(id=2, name='large', format='jpeg', width=1024, height=1024, auto_gen=True),
]


class MediaDB(SQLiteWriter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------
    # ImageType
    # ------------------------------------------------------------------

    def get_image_types(self, **filters) -> list[ImageType]:
        return IMAGE_TYPE_SHEMA.get(self.conn, **filters)

    def upsert_image_type(self, image_type: ImageType) -> None:
        with self.transaction() as tx:
            IMAGE_TYPE_SHEMA.upsert(tx, image_type)

    def delete_image_type(self, image_type_id: int) -> None:
        with self.transaction() as tx:
            IMAGE_TYPE_SHEMA.delete(tx, id=image_type_id)

    def ensure_default_image_types(self) -> None:
        """Seeds default image types if the table is empty. Call once after start()."""
        if not IMAGE_TYPE_SHEMA.get(self.conn):
            with self.transaction() as tx:
                IMAGE_TYPE_SHEMA.upsert(tx, _DEFAULT_IMAGE_TYPES)

    # ------------------------------------------------------------------
    # Image
    # ------------------------------------------------------------------

    def get_images(self, **filters) -> list[Image]:
        return IMAGE_SHEMA.get(self.conn, **filters)

    def upsert_images(self, images: list[Image]) -> None:
        with self.transaction() as tx:
            IMAGE_SHEMA.upsert(tx, images)

    def delete_image(self, type_id: int, sha1: str) -> None:
        with self.transaction() as tx:
            IMAGE_SHEMA.delete(tx, type_id=type_id, sha1=sha1)

    # ------------------------------------------------------------------
    # VectorType
    # ------------------------------------------------------------------

    def get_vector_types(self, **filters) -> list[VectorType]:
        return VECTOR_TYPE_SHEMA.get(self.conn, **filters)

    def upsert_vector_type(self, vector_type: VectorType) -> None:
        with self.transaction() as tx:
            VECTOR_TYPE_SHEMA.upsert(tx, vector_type)

    def delete_vector_type(self, vector_type_id: int) -> None:
        with self.transaction() as tx:
            VECTOR_TYPE_SHEMA.delete(tx, id=vector_type_id)

    # ------------------------------------------------------------------
    # Vector
    # ------------------------------------------------------------------

    def get_vectors(self, **filters) -> list[Vector]:
        return VECTOR_SHEMA.get(self.conn, **filters)

    def upsert_vectors(self, vectors: list[Vector]) -> None:
        with self.transaction() as tx:
            VECTOR_SHEMA.upsert(tx, vectors)

    # ------------------------------------------------------------------
    # ImageAtlas
    # ------------------------------------------------------------------

    def get_image_atlases(self, **filters) -> list[ImageAtlas]:
        return IMAGE_ATLAS_SHEMA.get(self.conn, **filters)

    def upsert_image_atlas(self, atlas: ImageAtlas) -> None:
        with self.transaction() as tx:
            IMAGE_ATLAS_SHEMA.upsert(tx, atlas)

    # ------------------------------------------------------------------
    # Map
    # ------------------------------------------------------------------

    def get_maps(self, **filters) -> list[Map]:
        return MAP_SHEMA.get(self.conn, **filters)

    def upsert_map(self, map_: Map) -> None:
        with self.transaction() as tx:
            MAP_SHEMA.upsert(tx, map_)

    def delete_map(self, map_id: int) -> None:
        with self.transaction() as tx:
            MAP_SHEMA.delete(tx, id=map_id)
