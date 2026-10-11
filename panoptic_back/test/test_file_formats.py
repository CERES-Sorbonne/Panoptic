import pytest
from PIL import Image as PilImage

from panoptic.core.file_source.local_reader import LocalFileSourceReader, _process_local_item
from panoptic.core.file_source.processing import IMAGE_EXTENSIONS

# extension → PIL format used to write the sample file
FORMATS = {
    '.jpg': 'JPEG', '.png': 'PNG', '.gif': 'GIF', '.webp': 'WEBP', '.tif': 'TIFF',
    '.avif': 'AVIF', '.bmp': 'BMP', '.jp2': 'JPEG2000',
}


def test_every_sample_format_is_imported():
    assert set(FORMATS) <= set(IMAGE_EXTENSIONS)


@pytest.mark.parametrize('ext,pil_format', FORMATS.items())
def test_local_import_scans_and_thumbnails_format(tmp_path, ext, pil_format):
    path = tmp_path / f'photo{ext.upper()}'  # extension match is case-insensitive
    PilImage.new('RGB', (64, 48), 'red').save(path, pil_format)
    (tmp_path / 'notes.txt').write_text('not an image')

    _, items = LocalFileSourceReader(None, str(tmp_path), image_types=[]).scan()
    assert [i.name for i in items] == [path.name]

    result = _process_local_item(str(path), [(1, 'webp', 32, 32)])
    assert (result['width'], result['height']) == (64, 48)
    [(type_id, data)] = result['images']
    assert type_id == 1 and data
