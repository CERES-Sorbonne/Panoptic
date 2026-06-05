from panoptic.core.databases.media.create import (
    VECTOR_TYPE_SHEMA, VECTOR_SHEMA, IMAGE_TYPE_SHEMA,
    IMAGE_SHEMA, IMAGE_ATLAS_SHEMA, MAP_SHEMA
)
from panoptic.core.databases.media.models import VectorType, Vector, ImageType, Image, ImageAtlas, Map
from panoptic.core.databases.sqlite_db import SQLiteWriter

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

    # ------------------------------------------------------------------
    # Image
    # ------------------------------------------------------------------

    def get_image_stats(self) -> dict[int, int]:
        rows = self.conn.execute(
            "SELECT type_id, COUNT(DISTINCT sha1) FROM images GROUP BY type_id"
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def get_images(self, **filters) -> list[Image]:
        return IMAGE_SHEMA.get(self.conn, **filters)

    def upsert_images(self, images: list[Image]) -> None:
        with self.transaction() as tx:
            IMAGE_SHEMA.upsert(tx, images)

    def delete_image(self, type_id: int, sha1: str) -> None:
        with self.transaction() as tx:
            IMAGE_SHEMA.delete(tx, type_id=type_id, sha1=sha1)

    def delete_media_for_sha1s(self, sha1s: list[str]) -> None:
        """Drop every stored image and vector for the given (now orphaned) sha1s.

        Best-effort cleanup invoked after structural deletes in the data DB; a leftover
        blob is only wasted disk, not a correctness issue.
        """
        if not sha1s:
            return
        with self.transaction() as tx:
            IMAGE_SHEMA.delete(tx, sha1=list(sha1s))
            VECTOR_SHEMA.delete(tx, sha1=list(sha1s))

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

    def get_vector_stats(self) -> dict:
        rows = self.conn.execute(
            "SELECT type_id, COUNT(DISTINCT sha1) FROM vectors GROUP BY type_id"
        ).fetchall()
        count = {r[0]: r[1] for r in rows} if rows else {}
        return {'count': count, 'sha1_count': 0}  # sha1_count overridden by Project

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
