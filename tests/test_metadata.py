from phota.metadata import extract_metadata
from tests.fixtures import make_jpeg


def test_extract_captured_at_and_camera(photo_dir):
    p = make_jpeg(
        photo_dir / "a.jpg",
        captured="2025:12:18 00:15:00",
        camera="X-T5",
        lens="XF23mm",
    )
    meta = extract_metadata(str(p), fallback_mtime=1000.0)
    assert meta["captured_at"] == "2025-12-18T00:15:00"
    assert meta["captured_approx"] is False
    assert meta["camera"] == "X-T5"
    assert meta["lens"] == "XF23mm"


def test_missing_exif_time_falls_back_to_mtime(photo_dir):
    p = make_jpeg(photo_dir / "b.jpg", captured=None)
    meta = extract_metadata(str(p), fallback_mtime=0.0)
    assert meta["captured_approx"] is True
    assert meta["captured_at"] == "1970-01-01T00:00:00"
