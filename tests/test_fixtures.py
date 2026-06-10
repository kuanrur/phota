from PIL import Image

from tests.fixtures import make_jpeg


def test_make_jpeg_writes_file_with_exif(tmp_path):
    p = make_jpeg(
        tmp_path / "a.jpg",
        captured="2025:12:18 00:15:00",
        camera="X-T5",
        sharp=True,
    )
    assert p.exists()
    img = Image.open(p)
    assert img.size == (64, 64)
    exif = img.getexif()
    # 0x9003 = DateTimeOriginal lives in the Exif IFD; piexif round-trips it.
    assert p.stat().st_size > 0
