from fastapi.testclient import TestClient
import time
from phota.server import create_app
from tests.fixtures import make_jpeg


def _setup(monkeypatch, tmp_path, n=3):
    monkeypatch.setenv('PHOTA_HOME', str(tmp_path / 'home'))
    src = tmp_path / 'f'; src.mkdir()
    for i in range(n):
        make_jpeg(src / f'p{i}.jpg', captured=f'2025:12:18 00:15:0{i}')
    return TestClient(create_app(None)), src


def test_progress_callback_counts(monkeypatch, tmp_path):
    from phota.engine import build_index
    src = tmp_path / 'f'; src.mkdir()
    for i in range(3):
        make_jpeg(src / f'p{i}.jpg', captured=f'2025:12:18 00:15:0{i}')
    calls = []
    build_index(src, db_path=str(tmp_path / 'i.db'), progress=lambda d, t: calls.append((d, t)))
    assert calls[0] == (0, 3) and calls[-1] == (3, 3)
    dones = [d for d, _ in calls]
    assert dones == sorted(dones)  # monotonic


def test_async_open_folder_and_status(monkeypatch, tmp_path):
    c, src = _setup(monkeypatch, tmp_path)
    r = c.post('/api/open-folder', json={'path': str(src)})
    assert r.status_code == 200 and r.json().get('indexing') is True
    deadline = time.time() + 30
    status = None
    while time.time() < deadline:
        status = c.get('/api/index-status').json()
        if not status['running']:
            break
        time.sleep(0.05)
    assert status is not None and status['running'] is False
    assert status['count'] == 3 and status['error'] is None
    assert c.get('/api/library').json()['count'] == 3


def test_open_folder_wait_true_is_synchronous(monkeypatch, tmp_path):
    c, src = _setup(monkeypatch, tmp_path)
    r = c.post('/api/open-folder', json={'path': str(src), 'wait': True})
    assert r.status_code == 200 and r.json()['count'] == 3
