from fastapi.testclient import TestClient
from phota.server import create_app
from phota.engine import build_index
from tests.fixtures import make_jpeg


def _client(photo_dir):
    make_jpeg(photo_dir / 'a.jpg', captured='2025:12:18 00:15:00', camera='X-T5')
    make_jpeg(photo_dir / 'b.jpg', captured='2025:12:18 00:16:00', camera='X-T5')
    build_index(photo_dir)
    return TestClient(create_app(str(photo_dir)))


def test_set_keep(photo_dir):
    c = _client(photo_dir)
    pid = c.get('/api/photos').json()[0]['id']
    assert c.post(f'/api/photos/{pid}/keep', json={'keep': True}).status_code == 200
    photos = {p['id']: p for p in c.get('/api/photos').json()}
    assert photos[pid]['keep'] is True


def test_album_flow(photo_dir):
    c = _client(photo_dir)
    ids = [p['id'] for p in c.get('/api/photos').json()]
    assert c.post('/api/albums', json={'name': 'Trip'}).status_code == 200
    c.post('/api/albums/Trip/photos', json={'ids': [ids[0]]})
    trip = [a for a in c.get('/api/albums').json() if a['name'] == 'Trip'][0]
    assert trip['count'] == 1
    photos = {p['id']: p for p in c.get('/api/photos').json()}
    assert 'Trip' in photos[ids[0]]['albums']
    c.request('DELETE', '/api/albums/Trip/photos', json={'ids': [ids[0]]})
    assert [a for a in c.get('/api/albums').json() if a['name'] == 'Trip'][0]['count'] == 0


def test_reveal_calls_opener(photo_dir, monkeypatch):
    import phota.server as server
    called = {}
    monkeypatch.setattr(server, 'reveal_in_finder', lambda path: called.setdefault('path', path))
    c = _client(photo_dir)
    pid = c.get('/api/photos').json()[0]['id']
    assert c.post(f'/api/reveal/{pid}').status_code == 200
    assert called['path'].endswith('.jpg')


def test_open_calls_default_app(photo_dir, monkeypatch):
    import phota.server as server
    called = {}
    monkeypatch.setattr(server, 'open_in_default_app', lambda path: called.setdefault('path', path))
    c = _client(photo_dir)
    pid = c.get('/api/photos').json()[0]['id']
    assert c.post(f'/api/open/{pid}').status_code == 200
    assert called['path'].endswith('.jpg')
