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
    shutter: tuple[int, int] | None = None,
    aperture: tuple[int, int] | None = None,
    gps: tuple[float, float] | None = None,
) -> Path:
    arr = _sharp_array() if sharp else _blurred_array()
    img = Image.fromarray(arr, mode="RGB")
    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    exif_dict["0th"][piexif.ImageIFD.Model] = camera.encode()
    exif_dict["Exif"][piexif.ExifIFD.LensModel] = lens.encode()
    if captured:
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = captured.encode()
    if shutter:
        exif_dict["Exif"][piexif.ExifIFD.ExposureTime] = shutter
    if aperture:
        exif_dict["Exif"][piexif.ExifIFD.FNumber] = aperture
    if gps:
        lat, lon = gps
        exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = _decimal_to_dms(abs(lat))
        exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = b"N" if lat >= 0 else b"S"
        exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = _decimal_to_dms(abs(lon))
        exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = b"E" if lon >= 0 else b"W"
    exif_bytes = piexif.dump(exif_dict)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "jpeg", exif=exif_bytes)
    return path


def make_png(path: Path) -> Path:
    """A minimal PNG so the scanner indexes it as a non-JPEG raster format."""
    img = Image.fromarray(_sharp_array(), mode="RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "png")
    return path


def make_svg(path: Path) -> Path:
    """A minimal SVG (text) so the scanner indexes it as a vector format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
    )
    return path


def _decimal_to_dms(value: float) -> list[tuple[int, int]]:
    degrees = int(value)
    minutes_float = (value - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    return [(degrees, 1), (minutes, 1), (round(seconds * 100), 100)]
