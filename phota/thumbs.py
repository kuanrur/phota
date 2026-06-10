from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

import phota.imageio  # noqa: F401  (registers the HEIF opener)
from phota.config import db_path, RAW_EXTS
from phota.models import Photo


def thumbs_dir() -> Path:
    return Path(db_path()).parent / "thumbs"


def previews_dir() -> Path:
    return Path(db_path()).parent / "previews"


def thumb_path(photo_id: str) -> Path:
    return thumbs_dir() / f"{photo_id}.jpg"


def preview_path(photo_id: str) -> Path:
    return previews_dir() / f"{photo_id}.jpg"


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


def _get_or_build(photo: Photo, target: Path, size: int, quality: int) -> str | None:
    if target.exists():
        return str(target)
    img = _load_color(photo.path)
    if img is None:
        return None
    img.thumbnail((size, size))
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(target, "JPEG", quality=quality)
    return str(target)


def get_or_build_thumb(photo: Photo, size: int = 256) -> str | None:
    """Return the path to a cached grid thumbnail, building it if needed."""
    return _get_or_build(photo, thumb_path(photo.id), size, quality=82)


def get_or_build_preview(photo: Photo, size: int = 1440) -> str | None:
    """Return the path to a cached high-res preview for culling (judging focus).

    Larger and higher-quality than the grid thumbnail. For raws this uses the
    embedded camera preview (often near full-res), so it stays fast.
    """
    return _get_or_build(photo, preview_path(photo.id), size, quality=90)
