from panoptic.core.databases.entity_schema import EntitySchema
from panoptic.core.databases.db_description import DbDescription
from panoptic.core.databases.media.models import VectorType, Vector, ImageType, Image, ImageAtlas, Map

VECTOR_TYPE_SHEMA = EntitySchema(VectorType, 'vector_types')
VECTOR_SHEMA = EntitySchema(Vector, 'vectors')
IMAGE_TYPE_SHEMA = EntitySchema(ImageType, 'image_types')
IMAGE_SHEMA = EntitySchema(Image, 'images')
IMAGE_ATLAS_SHEMA = EntitySchema(ImageAtlas, 'image_atlas')
MAP_SHEMA = EntitySchema(Map, 'maps')

ALL_SCHEMAS = [
    VECTOR_TYPE_SHEMA,
    VECTOR_SHEMA,
    IMAGE_TYPE_SHEMA,
    IMAGE_SHEMA,
    IMAGE_ATLAS_SHEMA,
    MAP_SHEMA
]

# Build the tables dictionary dynamically
tables_config = {}
for s in ALL_SCHEMAS:
    tables_config[s.table] = s.create_table_sql()
    if s.trackable:
        tables_config[f"{s.table}_log"] = s.create_log_table_sql()

datastore_desc = DbDescription(
    version=1,
    tables=tables_config,
    migrations={}
)