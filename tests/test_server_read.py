from fastapi.testclient import TestClient
from phota.server import create_app
from phota.engine import build_index
from tests.fixtures import make_jpeg


def _client(photo_dir):
    make_jpeg(photo_dir / 'a.jpg', captured='2025:12:18 00:15:00', camera='X-T5', sharp=True)
    make_jpeg(photo_dir / 'b.jpg', captured='2025:12:18 00:15:01', camera='X-T5', sharp=False)
    build_index(photo_dir)
    return TestClient(create_app(str(photo_dir)))


def test_library_summary(photo_dir):
    d = _client(photo_dir).get('/api/library').json()
    assert d['count'] == 2 and 'X-T5' in d['cameras']


def test_photos_list_and_shape(photo_dir):
    photos = _client(photo_dir).get('/api/photos').json()
    assert len(photos) == 2
    p = photos[0]
    for k in ('id','filename','captured_at','camera','series_id','sharpness','keep','albums','thumb_url'):
        assert k in p
    assert p['thumb_url'] == f"/api/thumb/{p['id']}"


def test_photos_filter_camera(photo_dir):
    c = _client(photo_dir)
    assert len(c.get('/api/photos?camera=X-T5').json()) == 2
    assert len(c.get('/api/photos?camera=Nope').json()) == 0


def test_thumb_returns_jpeg(photo_dir):
    c = _client(photo_dir)
    pid = c.get('/api/photos').json()[0]['id']
    r = c.get(f'/api/thumb/{pid}')
    assert r.status_code == 200 and r.headers['content-type'] == 'image/jpeg'


def test_thumb_unknown_404(photo_dir):
    assert _client(photo_dir).get('/api/thumb/nope').status_code == 404


def test_series_endpoint(photo_dir):
    s = _client(photo_dir).get('/api/series').json()
    assert isinstance(s, list)


def test_full_returns_jpeg(photo_dir):
    c = _client(photo_dir)
    pid = c.get('/api/photos').json()[0]['id']
    r = c.get(f'/api/full/{pid}')
    assert r.status_code == 200 and r.headers['content-type'] == 'image/jpeg'


def test_full_unknown_404(photo_dir):
    assert _client(photo_dir).get('/api/full/nope').status_code == 404
