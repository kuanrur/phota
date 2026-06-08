from pathlib import Path
from PIL import Image
from phota.thumbs import get_or_build_thumb
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
