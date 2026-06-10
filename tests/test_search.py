from fastapi.testclient import TestClient
from phota.server import create_app
from phota.engine import build_index
from tests.fixtures import make_jpeg


def _client(photo_dir):
    make_jpeg(photo_dir / 'a.jpg', captured='2025:12:18 00:15:00', camera='X-T5')
    build_index(photo_dir)
    return TestClient(create_app(str(photo_dir)))


def test_search_409_without_ai(photo_dir):
    assert _client(photo_dir).get('/api/search?q=cat').status_code == 409


def test_search_with_ai(photo_dir, monkeypatch):
    import phota.ai as ai

    class Fake:
        vision = True
        def available(self): return True
        def analyze_image(self, path): return {'caption': 'a cat', 'tags': ['cat'], 'subjects': ['cat'], 'aesthetic_score': 0.5}

    monkeypatch.setattr(ai, '_provider', lambda: Fake())
    c = _client(photo_dir)
    c.post('/api/ai/analyze')
    r = c.get('/api/search?q=cat')
    assert r.status_code == 200 and len(r.json()) >= 1


def test_settings_roundtrip_redacts_key(photo_dir):
    c = _client(photo_dir)
    c.post('/api/settings/ai', json={'provider': 'anthropic', 'api_key': 'secret'})
    s = c.get('/api/settings/ai').json()
    assert s['configured'] is True and s['provider'] == 'anthropic'
    assert 'secret' not in str(s) and 'api_key' not in s
