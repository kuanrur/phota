import os
from fastapi.testclient import TestClient
from phota.server import create_app
from phota.engine import build_index
from phota.exporter import build_export_plan
from phota.index import Index
from phota import store
from tests.fixtures import make_jpeg


def _client(photo_dir):
    make_jpeg(photo_dir / 'a.jpg', captured='2025:12:18 00:15:00', sharp=True)
    make_jpeg(photo_dir / 'b.jpg', captured='2025:12:18 00:16:00', sharp=True)
    build_index(photo_dir)
    return TestClient(create_app(str(photo_dir)))


def test_export_keepers_copies_only_keepers(photo_dir, tmp_path):
    c = _client(photo_dir)
    ids = [p['id'] for p in c.get('/api/photos').json()]
    c.post(f'/api/photos/{ids[0]}/keep', json={'keep': True})
    out = tmp_path / 'out'
    r = c.post('/api/export', json={'scope': 'keepers', 'mode': 'copy', 'out_dir': str(out)})
    assert r.status_code == 200 and r.json()['count'] == 1
    # originals intact
    assert (photo_dir / 'a.jpg').exists() and (photo_dir / 'b.jpg').exists()
    # exactly one file copied under out/keepers/
    copied = list((out / 'keepers').glob('*.jpg'))
    assert len(copied) == 1


def test_export_album(photo_dir, tmp_path):
    c = _client(photo_dir)
    ids = [p['id'] for p in c.get('/api/photos').json()]
    c.post('/api/albums', json={'name': 'X'})
    c.post('/api/albums/X/photos', json={'ids': [ids[0]]})
    out = tmp_path / 'out'
    r = c.post('/api/export', json={'scope': 'album:X', 'mode': 'copy', 'out_dir': str(out)})
    assert r.json()['count'] == 1
    assert len(list((out / 'X').glob('*.jpg'))) == 1


def test_export_move_writes_manifest(photo_dir, tmp_path):
    c = _client(photo_dir)
    ids = [p['id'] for p in c.get('/api/photos').json()]
    for i in ids:
        c.post(f'/api/photos/{i}/keep', json={'keep': True})
    out = tmp_path / 'out'
    r = c.post('/api/export', json={'scope': 'keepers', 'mode': 'move', 'out_dir': str(out)})
    d = r.json()
    assert d['count'] == 2 and os.path.exists(d['manifest_path'])


def _collision_client(photo_dir):
    # Two photos sharing a basename in different subdirs, with distinct
    # content (different capture times) so the index keeps both.
    make_jpeg(photo_dir / 'd1' / 'IMG.jpg', captured='2025:12:18 00:15:00', sharp=True)
    make_jpeg(photo_dir / 'd2' / 'IMG.jpg', captured='2025:12:18 00:16:00', sharp=True)
    build_index(photo_dir)
    return TestClient(create_app(str(photo_dir)))


def test_export_plan_decollides_duplicate_basenames(photo_dir):
    _collision_client(photo_dir)
    idx = Index()
    idx.init_schema()
    plan = build_export_plan(idx, 'all', '/tmp/out')
    dsts = [op.dst for op in plan.ops]
    assert len(plan.ops) == 2
    assert len(set(dsts)) == 2, f'destinations must be unique, got {dsts}'


def test_export_move_collision_keeps_originals_and_manifest(photo_dir, tmp_path):
    c = _collision_client(photo_dir)
    ids = [p['id'] for p in c.get('/api/photos').json()]
    for i in ids:
        c.post(f'/api/photos/{i}/keep', json={'keep': True})
    out = tmp_path / 'out'
    r = c.post('/api/export', json={'scope': 'keepers', 'mode': 'move', 'out_dir': str(out)})
    # Either it succeeds with both moved and a manifest, or it fails cleanly
    # (4xx) WITHOUT mutating the filesystem. A 500 with a half-done move and
    # no manifest is forbidden.
    assert r.status_code != 500
    if r.status_code == 200:
        d = r.json()
        assert d['count'] == 2 and os.path.exists(d['manifest_path'])
        assert len(list((out / 'keepers').glob('*.jpg'))) == 2
    else:
        # clean rejection: no original destroyed
        assert (photo_dir / 'd1' / 'IMG.jpg').exists()
        assert (photo_dir / 'd2' / 'IMG.jpg').exists()
