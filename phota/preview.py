from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from phota.config import RAW_EXTS

_MAX_EDGE = 512


def _downscale_gray(img: Image.Image) -> np.ndarray:
    img = img.convert("L")
    img.thumbnail((_MAX_EDGE, _MAX_EDGE))
    return np.asarray(img)


def load_preview(path: str) -> np.ndarray | None:
    """Return a small grayscale ndarray for analysis, or None on failure.

    For raws, use the embedded preview via rawpy.thumb so we never fully
    demosaic a 30MB file just to score it.
    """
    p = Path(path)
    if not p.exists():
        return None
    try:
        if p.suffix.lower() in RAW_EXTS:
            import rawpy

            with rawpy.imread(str(p)) as raw:
                thumb = raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                import io

                img = Image.open(io.BytesIO(thumb.data))
            else:  # BITMAP
                img = Image.fromarray(thumb.data)
            return _downscale_gray(img)
        return _downscale_gray(Image.open(p))
    except Exception:
        return None
