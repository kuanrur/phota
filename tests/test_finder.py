from fastapi.testclient import TestClient
from phota.server import create_app
import phota.server as server
from tests.fixtures import make_jpeg


def test_finder_folders_listed(monkeypatch, tmp_path):
    d = tmp_path / 'Downloads'; d.mkdir()
    monkeypatch.setattr(server, 'detect_finder_folders', lambda: ([str(d)], None))
    c = TestClient(create_app(None))
    r = c.get('/api/finder-folders').json()
    assert r['error'] is None
    assert r['folders'][0]['path'] == str(d) and r['folders'][0]['name'] == 'Downloads'


def test_finder_folders_permission_error(monkeypatch):
    monkeypatch.setattr(server, 'detect_finder_folders', lambda: ([], 'permission'))
    c = TestClient(create_app(None))
    r = c.get('/api/finder-folders').json()
    assert r['error'] == 'permission' and r['folders'] == []


def test_open_folder_switches_active(monkeypatch, tmp_path):
    monkeypatch.setenv('PHOTA_HOME', str(tmp_path / 'home'))  # isolate libraries from real ~/.phota
    src = tmp_path / 'shoot'; src.mkdir()
    make_jpeg(src / 'a.jpg', captured='2025:12:18 00:15:00')
    make_jpeg(src / 'b.jpg', captured='2025:12:18 00:16:00')
    c = TestClient(create_app(None))
    r = c.post('/api/open-folder', json={'path': str(src)})
    assert r.status_code == 200 and r.json()['count'] == 2
    photos = c.get('/api/photos').json()
    assert len(photos) == 2


def test_finder_url_to_path_decodes_and_filters():
    from phota.server import _finder_url_to_path
    assert _finder_url_to_path('file:///Users/kj/Downloads/') == '/Users/kj/Downloads'
    assert _finder_url_to_path('file:///Users/kj/My%20Photos/') == '/Users/kj/My Photos'
    assert _finder_url_to_path('') is None
    assert _finder_url_to_path('x-special:///Recents') is None  # smart folders skipped
