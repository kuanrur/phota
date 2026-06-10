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


def _rational_value(raw) -> float:
    num, den = raw
    return num / den


def _format_shutter(raw) -> str | None:
    try:
        num, den = raw
        value = num / den
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if num == 1:
        return f"1/{den}"
    if value >= 1:
        return f"{value:g}s"
    return f"{num}/{den}"


def _format_aperture(raw) -> str | None:
    try:
        value = _rational_value(raw)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return f"f/{value:g}"


def _dms_to_decimal(dms, ref) -> float:
    degrees = _rational_value(dms[0])
    minutes = _rational_value(dms[1])
    seconds = _rational_value(dms[2])
    decimal = degrees + (minutes / 60) + (seconds / 3600)
    if _decode(ref) in {"S", "W"}:
        return -decimal
    return decimal


def _extract_gps(gps_ifd: dict) -> tuple[float | None, float | None]:
    try:
        lat = _dms_to_decimal(
            gps_ifd[piexif.GPSIFD.GPSLatitude],
            gps_ifd[piexif.GPSIFD.GPSLatitudeRef],
        )
        lon = _dms_to_decimal(
            gps_ifd[piexif.GPSIFD.GPSLongitude],
            gps_ifd[piexif.GPSIFD.GPSLongitudeRef],
        )
    except (KeyError, TypeError, ValueError, ZeroDivisionError, IndexError):
        return None, None
    return lat, lon


def extract_metadata(path: str, fallback_mtime: float) -> dict:
    meta = {
        "captured_at": None,
        "captured_approx": False,
        "camera": None,
        "lens": None,
        "iso": None,
        "shutter": None,
        "aperture": None,
        "gps_lat": None,
        "gps_lon": None,
    }
    try:
        exif = piexif.load(path)
    except Exception:
        exif = {"0th": {}, "Exif": {}, "GPS": {}}

    zeroth = exif.get("0th", {})
    exif_ifd = exif.get("Exif", {})
    gps_ifd = exif.get("GPS", {})

    meta["camera"] = _decode(zeroth.get(piexif.ImageIFD.Model))
    meta["lens"] = _decode(exif_ifd.get(piexif.ExifIFD.LensModel))
    iso = exif_ifd.get(piexif.ExifIFD.ISOSpeedRatings)
    meta["iso"] = int(iso) if isinstance(iso, int) else None
    meta["shutter"] = _format_shutter(exif_ifd.get(piexif.ExifIFD.ExposureTime))
    meta["aperture"] = _format_aperture(exif_ifd.get(piexif.ExifIFD.FNumber))
    meta["gps_lat"], meta["gps_lon"] = _extract_gps(gps_ifd)

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
