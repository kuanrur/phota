from phota.scan import scan_dir
from tests.fixtures import make_jpeg


def test_scan_finds_images_and_assigns_kind(photo_dir):
    make_jpeg(photo_dir / "a.jpg")
    make_jpeg(photo_dir / "b.JPG")
    (photo_dir / "notes.txt").write_text("ignore me")
    photos = scan_dir(photo_dir)
    assert len(photos) == 2
    assert all(p.kind == "jpeg" for p in photos)
    assert {p.filename for p in photos} == {"a.jpg", "b.JPG"}


def test_scan_id_is_content_stable(photo_dir):
    make_jpeg(photo_dir / "a.jpg")
    first = scan_dir(photo_dir)[0].id
    second = scan_dir(photo_dir)[0].id
    assert first == second
