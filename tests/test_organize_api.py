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


def test_sort_by_date_renames_in_order(monkeypatch, tmp_path):
    c, src = _client(monkeypatch, tmp_path, [
        ("z.jpg", {"captured": "2025:12:18 00:15:00"}),
        ("a.jpg", {"captured": "2025:12:18 09:00:00"}),
    ])
    r = c.post("/api/organize", json={"action": "sort_by_date"})
    assert r.status_code == 200 and r.json()["renamed"] == 2
    names = sorted(p.name for p in src.iterdir() if p.suffix == ".jpg")
    # z.jpg shot earlier -> 001_, a.jpg later -> 002_
    assert names == ["001_z.jpg", "002_a.jpg"]


def test_by_camera_groups(monkeypatch, tmp_path):
    c, src = _client(monkeypatch, tmp_path, [
        ("a.jpg", {"captured": "2025:12:18 00:15:00", "camera": "X-M5"}),
        ("b.jpg", {"captured": "2025:12:18 00:16:00", "camera": "EOS"}),
    ])
    r = c.post("/api/organize", json={"action": "by_camera"})
    assert r.json()["moved"] == 2
    assert (src / "X-M5" / "a.jpg").exists() and (src / "EOS" / "b.jpg").exists()


def test_by_day_groups(monkeypatch, tmp_path):
    c, src = _client(monkeypatch, tmp_path, [
        ("a.jpg", {"captured": "2025:12:18 00:15:00"}),
        ("b.jpg", {"captured": "2025:12:25 00:15:00"}),
    ])
    r = c.post("/api/organize", json={"action": "by_day"})
    assert r.json()["moved"] == 2
    assert (src / "2025-12-18" / "a.jpg").exists() and (src / "2025-12-25" / "b.jpg").exists()


def test_duplicates_moved(monkeypatch, tmp_path):
    import shutil
    c, src = _client(monkeypatch, tmp_path, [
        ("a.jpg", {"captured": "2025:12:18 00:15:00", "sharp": True}),
    ])
    shutil.copy2(src / "a.jpg", src / "a_copy.jpg")  # exact duplicate
    c.post("/api/open-folder", json={"path": str(src), "wait": True})  # re-index to pick up the copy
    r = c.post("/api/organize", json={"action": "duplicates"})
    assert r.json()["moved"] == 1
    assert (src / "_duplicates").exists() and len(list((src / "_duplicates").glob("*.jpg"))) == 1


def test_unknown_action_400(monkeypatch, tmp_path):
    c, src = _client(monkeypatch, tmp_path, [("a.jpg", {"captured": "2025:12:18 00:15:00"})])
    assert c.post("/api/organize", json={"action": "bogus"}).status_code == 400
