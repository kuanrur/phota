import sqlite3

from phota import store
from phota.index import Index
from phota.models import Photo

# Legacy photos schema (pre-keep), mirroring databases created before the
# keep column existed. Used to exercise init_schema's migration path.
_LEGACY_PHOTOS_DDL = """
CREATE TABLE photos (
    id TEXT PRIMARY KEY,
    path TEXT, filename TEXT, kind TEXT,
    size INTEGER, mtime REAL,
    captured_at TEXT, captured_approx INTEGER,
    camera TEXT, lens TEXT, iso INTEGER,
    shutter TEXT, aperture TEXT,
    gps_lat REAL, gps_lon REAL,
    sharpness REAL, exposure_score REAL,
    phash TEXT, series_id INTEGER,
    error TEXT, analyzed_at TEXT
);
"""


def _seed(idx, pid):
    idx.upsert_photo(Photo(id=pid, path=f'/x/{pid}.jpg', filename=f'{pid}.jpg', kind='jpeg'))


def test_keep_flag_roundtrip():
    idx = Index(); idx.init_schema()
    _seed(idx, 'a')
    assert store.get_keep(idx, 'a') is None
    store.set_keep(idx, 'a', True)
    assert store.get_keep(idx, 'a') is True
    store.set_keep(idx, 'a', False)
    assert store.get_keep(idx, 'a') is False
    store.set_keep(idx, 'a', None)
    assert store.get_keep(idx, 'a') is None


def test_album_crud_and_membership():
    idx = Index(); idx.init_schema()
    for p in ('a', 'b', 'c'):
        _seed(idx, p)
    store.create_album(idx, 'Iceland')
    assert [a['name'] for a in store.list_albums(idx)] == ['Iceland']
    store.add_to_album(idx, 'Iceland', ['a', 'b'])
    store.add_to_album(idx, 'Iceland', ['a'])  # idempotent
    assert sorted(store.photos_in_album(idx, 'Iceland')) == ['a', 'b']
    assert store.list_albums(idx)[0]['count'] == 2
    assert store.albums_for(idx, 'a') == ['Iceland']
    store.remove_from_album(idx, 'Iceland', ['a'])
    assert store.photos_in_album(idx, 'Iceland') == ['b']
    store.delete_album(idx, 'Iceland')
    assert store.list_albums(idx) == []


def test_existing_photo_roundtrip_still_works():
    idx = Index(); idx.init_schema()
    _seed(idx, 'z')
    assert idx.get_photo('z').filename == 'z.jpg'


def test_init_schema_migrates_legacy_db_missing_keep(tmp_path):
    """A pre-existing photos table without 'keep' must gain the column on init."""
    dbp = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(dbp))
    conn.executescript(_LEGACY_PHOTOS_DDL)
    conn.commit()
    conn.close()

    idx = Index(str(dbp))
    idx.init_schema()

    cols = [r[1] for r in idx.conn.execute("PRAGMA table_info(photos)").fetchall()]
    assert "keep" in cols
    # Upsert / keep operations must work against the migrated table.
    _seed(idx, "a")
    store.set_keep(idx, "a", True)
    assert store.get_keep(idx, "a") is True


def test_reupsert_preserves_keep_flag():
    """Rescanning a photo (re-upsert) must not erase a user's keep decision."""
    idx = Index(); idx.init_schema()
    _seed(idx, "a")
    store.set_keep(idx, "a", True)
    assert store.get_keep(idx, "a") is True
    _seed(idx, "a")  # simulate rescan: fresh Photo has keep=None
    assert store.get_keep(idx, "a") is True
    # A user-cleared keep (False) must also survive a rescan.
    store.set_keep(idx, "a", False)
    _seed(idx, "a")
    assert store.get_keep(idx, "a") is False
