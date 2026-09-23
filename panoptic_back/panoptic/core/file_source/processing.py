import hashlib
import io
from typing import Callable, Optional

# (type_id, format, max_width, max_height)
ImageTypeSpec = tuple[int, str, int | None, int | None]


def render(img, fmt: str, max_w: int | None, max_h: int | None) -> bytes:
    """Resize to fit within (max_w, max_h) — both optional — then encode."""
    copy = img.copy()
    if max_w or max_h:
        copy.thumbnail((max_w or 10 ** 6, max_h or 10 ** 6))
    buf = io.BytesIO()
    # PIL uses 'jpeg' not 'jpg'
    copy.save(buf, format='jpeg' if fmt.lower() in ('jpg', 'jpeg') else fmt)
    return buf.getvalue()


def process_bytes(
    raw: bytes,
    image_types: list[ImageTypeSpec],
    on_pil_error: Optional[Callable[[Exception], None]] = None,
) -> dict:
    """sha1 + PIL dimensions/format + a rendition per auto_gen image type.

    Source-agnostic: shared by every FileSourceReader so a locally-read file and a
    downloaded IIIF canvas go through the exact same hashing/thumbnailing code.
    Returns {'sha1', 'width', 'height', 'format', 'images': [(type_id, bytes), ...]}.
    """
    from PIL import Image as PilImage

    sha1 = hashlib.sha1(raw).hexdigest()
    width = height = None
    fmt = None
    images: list[tuple[int, bytes]] = []

    try:
        with PilImage.open(io.BytesIO(raw)) as img:
            width, height = img.size
            fmt = (img.format or '').lower() or None
            if image_types:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.load()
                for type_id, image_fmt, max_w, max_h in image_types:
                    images.append((type_id, render(img, image_fmt, max_w, max_h)))
    except Exception as e:
        if on_pil_error:
            on_pil_error(e)

    return {'sha1': sha1, 'width': width, 'height': height, 'format': fmt, 'images': images}
