from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from phota.config import db_path, RAW_EXTS
from phota.models import Photo


def thumbs_dir() -> Path:
    return Path(db_path()).parent / "thumbs"


def thumb_path(photo_id: str) -> Path:
    return thumbs_dir() / f"{photo_id}.jpg"


def _load_color(path: str) -> Image.Image | None:
    """Return an RGB PIL image for the photo, or None on failure."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        if p.suffix.lower() in RAW_EXTS:
            import rawpy

            with rawpy.imread(str(p)) as raw:
                thumb = raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                img = Image.open(io.BytesIO(thumb.data))
            else:  # BITMAP
                img = Image.fromarray(thumb.data)
        else:
            img = Image.open(p)
        return img.convert("RGB")
    except Exception:
        return None


def get_or_build_thumb(photo: Photo, size: int = 256) -> str | None:
    """Return the path to a cached JPEG thumbnail, building it if needed."""
    tp = thumb_path(photo.id)
    if tp.exists():
        return str(tp)
    img = _load_color(photo.path)
    if img is None:
        return None
    img.thumbnail((size, size))
    thumbs_dir().mkdir(parents=True, exist_ok=True)
    img.save(tp, "JPEG")
    return str(tp)
