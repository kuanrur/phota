from __future__ import annotations

import cv2
import imagehash
import numpy as np
from PIL import Image

from phota.preview import load_preview, _MAX_EDGE


def _sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _exposure_score(gray: np.ndarray) -> float:
    """1.0 = well exposed; lower = more clipped highlights/shadows."""
    hist = np.histogram(gray, bins=256, range=(0, 255))[0]
    total = gray.size
    clipped = (hist[0] + hist[255]) / total
    return float(max(0.0, 1.0 - clipped))


def score_photo(path: str) -> dict:
    gray = load_preview(path)
    if gray is None:
        return {"sharpness": None, "exposure_score": None, "phash": None}
    phash = str(imagehash.phash(Image.fromarray(gray)))
    return {
        "sharpness": _sharpness(gray),
        "exposure_score": _exposure_score(gray),
        "phash": phash,
    }
