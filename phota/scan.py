from __future__ import annotations

import hashlib
from pathlib import Path

from phota.config import JPEG_EXTS, RAW_EXTS, TIFF_EXTS, IMAGE_EXTS
from phota.models import Photo


def _kind_for(ext: str) -> str:
    ext = ext.lower()
    if ext in JPEG_EXTS:
        return "jpeg"
    if ext in RAW_EXTS:
        return "raw"
    if ext in TIFF_EXTS:
        return "tiff"
    return "other"


def _content_id(path: Path) -> str:
    """Hash size + first/last 64KB. Fast and stable for large raws."""
    h = hashlib.sha256()
    size = path.stat().st_size
    h.update(str(size).encode())
    with path.open("rb") as f:
        h.update(f.read(65536))
        if size > 65536:
            f.seek(-65536, 2)
            h.update(f.read(65536))
    return h.hexdigest()[:16]


def scan_dir(directory) -> list[Photo]:
    directory = Path(directory)
    photos: list[Photo] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            continue
        stat = path.stat()
        photos.append(
            Photo(
                id=_content_id(path),
                path=str(path),
                filename=path.name,
                kind=_kind_for(path.suffix),
                size=stat.st_size,
                mtime=stat.st_mtime,
            )
        )
    return photos
