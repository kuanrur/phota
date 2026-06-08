from pathlib import Path
from PIL import Image
from phota.thumbs import get_or_build_thumb, get_or_build_preview
from phota.models import Photo
from tests.fixtures import make_jpeg


def test_build_and_cache_thumb(photo_dir):
    p = make_jpeg(photo_dir / 'a.jpg', sharp=True)
    photo = Photo(id='a', path=str(p), filename='a.jpg', kind='jpeg')
    t = get_or_build_thumb(photo)
    assert t is not None and Path(t).exists()
    assert max(Image.open(t).size) <= 256
    mtime1 = Path(t).stat().st_mtime
    t2 = get_or_build_thumb(photo)
    assert Path(t2).stat().st_mtime == mtime1  # cached, not rebuilt


def test_unbuildable_returns_none():
    photo = Photo(id='z', path='/no/such.jpg', filename='z.jpg', kind='jpeg')
    assert get_or_build_thumb(photo) is None


def test_preview_keeps_more_resolution_than_thumb(photo_dir):
    # an 800x600 source: thumb caps at 256, preview should preserve more detail
    big = photo_dir / 'big.jpg'
    Image.new('RGB', (800, 600), (120, 90, 60)).save(big, 'JPEG')
    photo = Photo(id='big', path=str(big), filename='big.jpg', kind='jpeg')
    thumb = get_or_build_thumb(photo)
    preview = get_or_build_preview(photo)
    assert preview is not None and Path(preview).exists()
    assert max(Image.open(thumb).size) <= 256
    assert max(Image.open(preview).size) > 256  # genuinely higher-res
    assert max(Image.open(preview).size) <= 1440
    # cached on second call
    mtime1 = Path(preview).stat().st_mtime
    assert Path(get_or_build_preview(photo)).stat().st_mtime == mtime1


def test_preview_unbuildable_returns_none():
    photo = Photo(id='z', path='/no/such.jpg', filename='z.jpg', kind='jpeg')
    assert get_or_build_preview(photo) is None
