from fastapi.testclient import TestClient
from phota.server import create_app
from tests.fixtures import make_jpeg


def _client(monkeypatch, tmp_path, photos):
    monkeypatch.setenv("PHOTA_HOME", str(tmp_path / "home"))
    src = tmp_path / "messy"; src.mkdir()
    for name, kw in photos:
        make_jpeg(src / name, **kw)
    c = TestClient(create_app(None))
    c.post("/api/open-folder", json={"path": str(src), "wait": True})
    return c, src


def test_rename_dry_run_moves_nothing(monkeypatch, tmp_path):
    c, src = _client(monkeypatch, tmp_path, [
        ("z.jpg", {"captured": "2025:08:07 09:00:00"}),
        ("a.jpg", {"captured": "2025:08:07 08:00:00"}),
    ])
    r = c.post("/api/rename", json={"fmt": "number", "dry_run": True})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    # examples reflect the planned mapping (sorted by capture: a then z)
    assert body["examples"] == [
        {"from": "a.jpg", "to": "001.jpg"},
        {"from": "z.jpg", "to": "002.jpg"},
    ]
    # nothing moved on disk
    names = sorted(p.name for p in src.iterdir() if p.suffix == ".jpg")
    assert names == ["a.jpg", "z.jpg"]


def test_rename_real_renames_and_reindexes(monkeypatch, tmp_path):
    c, src = _client(monkeypatch, tmp_path, [
        ("z.jpg", {"captured": "2025:08:07 09:00:00"}),
        ("a.jpg", {"captured": "2025:08:07 08:00:00"}),
    ])
    r = c.post("/api/rename", json={"fmt": "number"})
    assert r.status_code == 200 and r.json()["renamed"] == 2
    names = sorted(p.name for p in src.iterdir() if p.suffix == ".jpg")
    assert names == ["001.jpg", "002.jpg"]
    # re-indexed: the library now reflects the new filenames
    photos = c.get("/api/photos").json()
    assert sorted(p["filename"] for p in photos) == ["001.jpg", "002.jpg"]


def test_rename_conflict_returns_409(monkeypatch, tmp_path):
    c, src = _client(monkeypatch, tmp_path, [
        ("a.jpg", {"captured": "2025:08:07 08:00:00"}),
    ])
    # A foreign, non-photo entry (a directory) already occupies the target slot
    # 001.jpg. It is not part of the rename plan, so rename_files must refuse to
    # clobber it -> 409. (A foreign *.jpg file would be indexed and become part
    # of the plan; a directory is skipped by the scanner.)
    (src / "001.jpg").mkdir()
    r = c.post("/api/rename", json={"fmt": "number"})
    assert r.status_code == 409


def test_rename_bad_fmt_returns_400(monkeypatch, tmp_path):
    c, src = _client(monkeypatch, tmp_path, [
        ("a.jpg", {"captured": "2025:08:07 08:00:00"}),
    ])
    assert c.post("/api/rename", json={"fmt": "bogus"}).status_code == 400


def test_rename_custom_empty_word_returns_400(monkeypatch, tmp_path):
    c, src = _client(monkeypatch, tmp_path, [
        ("a.jpg", {"captured": "2025:08:07 08:00:00"}),
    ])
    assert c.post("/api/rename", json={"fmt": "custom", "word": "///"}).status_code == 400
