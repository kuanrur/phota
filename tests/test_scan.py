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


def test_scan_recognizes_heic_png_svg(photo_dir):
    from PIL import Image
    import phota.imageio  # register heif
    # png (Pillow native), heic (pillow-heif), svg (vector, scanned only)
    Image.new('RGB', (32, 32), (10, 20, 30)).save(photo_dir / 'a.png')
    Image.new('RGB', (32, 32), (40, 50, 60)).save(photo_dir / 'b.heic', format='HEIF')
    (photo_dir / 'c.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    photos = scan_dir(photo_dir)
    names = {p.filename for p in photos}
    assert names == {'a.png', 'b.heic', 'c.svg'}
