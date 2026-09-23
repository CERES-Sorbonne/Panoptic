from pathlib import Path

import numpy as np

from panoptic.core.databases.media.media_db import MediaDB, _DEFAULT_IMAGE_TYPES
from panoptic.core.databases.media.models import ImageType, Image, VectorType, Vector, ImageAtlas, Map
from panoptic.core.databases.media.create import datastore_desc

media_db_path = Path("~/tmp/media.db").expanduser()


def _setup() -> MediaDB:
    media_db_path.parent.mkdir(parents=True, exist_ok=True)
    if media_db_path.exists():
        media_db_path.unlink()
    db = MediaDB(str(media_db_path), datastore_desc)
    db.start()
    return db


# ------------------------------------------------------------------
# ImageType
# ------------------------------------------------------------------

def test_ensure_default_image_types_seeds_on_empty_db():
    db = _setup()
    assert db.get_image_types() == []
    db.ensure_default_image_types()
    types = db.get_image_types()
    assert len(types) == len(_DEFAULT_IMAGE_TYPES)
    names = {t.name for t in types}
    assert 'small' in names
    assert 'large' in names


def test_ensure_default_image_types_does_not_duplicate():
    db = _setup()
    db.ensure_default_image_types()
    db.ensure_default_image_types()
    assert len(db.get_image_types()) == len(_DEFAULT_IMAGE_TYPES)


def test_upsert_image_type_adds_new():
    db = _setup()
    it = ImageType(id=10, name='preview', format='webp', width=512, height=512, auto_gen=True)
    db.upsert_image_type(it)
    result = db.get_image_types(id=10)
    assert len(result) == 1
    assert result[0].name == 'preview'
    assert result[0].format == 'webp'


def test_upsert_image_type_updates_existing():
    db = _setup()
    db.upsert_image_type(ImageType(id=5, name='thumb', format='jpeg', width=128, height=128))
    db.upsert_image_type(ImageType(id=5, name='thumb', format='webp', width=256, height=256))
    result = db.get_image_types(id=5)
    assert len(result) == 1
    assert result[0].format == 'webp'
    assert result[0].width == 256


def test_delete_image_type():
    db = _setup()
    db.upsert_image_type(ImageType(id=7, name='raw', format='png', width=None, height=None))
    assert len(db.get_image_types(id=7)) == 1
    db.delete_image_type(7)
    assert db.get_image_types(id=7) == []


def test_auto_gen_field_stored_and_retrieved():
    db = _setup()
    db.upsert_image_type(ImageType(id=1, name='small', format='jpeg', width=256,  height=256,  auto_gen=True))
    db.upsert_image_type(ImageType(id=2, name='large', format='jpeg', width=1024, height=1024, auto_gen=False))

    active   = [t for t in db.get_image_types() if t.auto_gen]
    inactive = [t for t in db.get_image_types() if not t.auto_gen]

    assert len(active) == 1 and active[0].name == 'small'
    assert len(inactive) == 1 and inactive[0].name == 'large'


def test_auto_gen_defaults_to_true():
    db = _setup()
    db.upsert_image_type(ImageType(id=3, name='mid', format='jpeg', width=512, height=512))
    assert db.get_image_types(id=3)[0].auto_gen is True


# ------------------------------------------------------------------
# Image
# ------------------------------------------------------------------

def test_upsert_and_get_images():
    db = _setup()
    img = Image(type_id=1, sha1='abc123', data=b'\xff\xd8\xff')
    db.upsert_images([img])
    result = db.get_images(sha1='abc123')
    assert len(result) == 1
    assert result[0].data == b'\xff\xd8\xff'
    assert result[0].type_id == 1


def test_upsert_images_updates_existing():
    db = _setup()
    db.upsert_images([Image(type_id=1, sha1='aaa', data=b'\x00')])
    db.upsert_images([Image(type_id=1, sha1='aaa', data=b'\x01\x02')])
    result = db.get_images(sha1='aaa')
    assert len(result) == 1
    assert result[0].data == b'\x01\x02'


def test_delete_image():
    db = _setup()
    db.upsert_images([Image(type_id=2, sha1='bbb', data=b'\xAA')])
    assert len(db.get_images(sha1='bbb')) == 1
    db.delete_image(type_id=2, sha1='bbb')
    assert db.get_images(sha1='bbb') == []


# ------------------------------------------------------------------
# VectorType
# ------------------------------------------------------------------

def test_upsert_and_get_vector_types():
    db = _setup()
    vt = VectorType(id=1, source='clip', params={'model': 'ViT-B/32'})
    db.upsert_vector_type(vt)
    result = db.get_vector_types(id=1)
    assert len(result) == 1
    assert result[0].source == 'clip'
    assert result[0].params['model'] == 'ViT-B/32'


def test_delete_vector_type():
    db = _setup()
    db.upsert_vector_type(VectorType(id=3, source='dino', params={}))
    assert len(db.get_vector_types(id=3)) == 1
    db.delete_vector_type(3)
    assert db.get_vector_types(id=3) == []


# ------------------------------------------------------------------
# Vector
# ------------------------------------------------------------------

def test_upsert_and_get_vectors():
    db = _setup()
    arr = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    db.upsert_vectors([Vector(type_id=1, sha1='sha_vec', data=arr)])
    result = db.get_vectors(sha1='sha_vec')
    assert len(result) == 1
    assert np.allclose(result[0].data, arr)


# ------------------------------------------------------------------
# ImageAtlas
# ------------------------------------------------------------------

def test_upsert_and_get_image_atlas():
    db = _setup()
    atlas = ImageAtlas(
        id=1, atlas_nb=2, width=4096, height=4096,
        cell_width=64, cell_height=64,
        sha1_mapping={'abc': (0, 0), 'def': (0, 1)}
    )
    db.upsert_image_atlas(atlas)
    result = db.get_image_atlases(id=1)
    assert len(result) == 1
    assert result[0].atlas_nb == 2
    assert result[0].sha1_mapping['def'] == (0, 1)


# ------------------------------------------------------------------
# Map
# ------------------------------------------------------------------

def test_upsert_and_get_map():
    db = _setup()
    m = Map(id=1, source='umap', name='My Map', key='umap_clip', count=500, data={'points': []})
    db.upsert_map(m)
    result = db.get_maps(id=1)
    assert len(result) == 1
    assert result[0].name == 'My Map'
    assert result[0].count == 500


def test_delete_map():
    db = _setup()
    db.upsert_map(Map(id=2, source='pca', name='PCA', key='pca_1', count=100, data=None))
    assert len(db.get_maps(id=2)) == 1
    db.delete_map(2)
    assert db.get_maps(id=2) == []


def test_upsert_map_updates_existing():
    db = _setup()
    db.upsert_map(Map(id=3, source='umap', name='Old', key='k', count=10, data=None))
    db.upsert_map(Map(id=3, source='umap', name='New', key='k', count=20, data={'x': 1}))
    result = db.get_maps(id=3)
    assert len(result) == 1
    assert result[0].name == 'New'
    assert result[0].count == 20
