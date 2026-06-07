from pathlib import Path

import numpy as np
import piexif
from PIL import Image


def _sharp_array() -> np.ndarray:
    # High-frequency checkerboard => high Laplacian variance (sharp).
    a = np.indices((64, 64)).sum(axis=0) % 2 * 255
    return np.stack([a, a, a], axis=-1).astype("uint8")


def _blurred_array() -> np.ndarray:
    # Smooth gradient => low Laplacian variance (blurred).
    g = np.tile(np.linspace(0, 255, 64), (64, 1))
    return np.stack([g, g, g], axis=-1).astype("uint8")


def make_jpeg(
    path: Path,
    captured: str | None = None,
    camera: str = "TestCam",
    lens: str = "TestLens",
    sharp: bool = True,
) -> Path:
    arr = _sharp_array() if sharp else _blurred_array()
    img = Image.fromarray(arr, mode="RGB")
    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    exif_dict["0th"][piexif.ImageIFD.Model] = camera.encode()
    exif_dict["Exif"][piexif.ExifIFD.LensModel] = lens.encode()
    if captured:
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = captured.encode()
    exif_bytes = piexif.dump(exif_dict)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "jpeg", exif=exif_bytes)
    return path
