from __future__ import annotations

from datetime import datetime, timezone

import piexif


def _decode(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", "ignore").strip("\x00").strip() or None
    return str(value).strip() or None


def _parse_exif_datetime(raw: str) -> str | None:
    try:
        dt = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
        return dt.isoformat()
    except (ValueError, TypeError):
        return None


def extract_metadata(path: str, fallback_mtime: float) -> dict:
    meta = {
        "captured_at": None,
        "captured_approx": False,
        "camera": None,
        "lens": None,
        "iso": None,
        "shutter": None,
        "aperture": None,
    }
    try:
        exif = piexif.load(path)
    except Exception:
        exif = {"0th": {}, "Exif": {}}

    zeroth = exif.get("0th", {})
    exif_ifd = exif.get("Exif", {})

    meta["camera"] = _decode(zeroth.get(piexif.ImageIFD.Model))
    meta["lens"] = _decode(exif_ifd.get(piexif.ExifIFD.LensModel))
    iso = exif_ifd.get(piexif.ExifIFD.ISOSpeedRatings)
    meta["iso"] = int(iso) if isinstance(iso, int) else None

    dt_raw = _decode(exif_ifd.get(piexif.ExifIFD.DateTimeOriginal))
    parsed = _parse_exif_datetime(dt_raw) if dt_raw else None
    if parsed:
        meta["captured_at"] = parsed
    else:
        meta["captured_at"] = datetime.fromtimestamp(
            fallback_mtime, tz=timezone.utc
        ).replace(tzinfo=None).isoformat()
        meta["captured_approx"] = True
    return meta
