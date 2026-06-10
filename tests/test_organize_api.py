from fastapi.testclient import TestClient
from phota.server import create_app
from tests.fixtures import make_jpeg, make_png, make_svg


def _client(monkeypatch, tmp_path, photos):
    monkeypatch.setenv("PHOTA_HOME", str(tmp_path / "home"))
    src = tmp_path / "messy"; src.mkdir()
    for name, kw in photos:
        make_jpeg(src / name, **kw)
    c = TestClient(create_app(None))
    c.post("/api/open-folder", json={"path": str(src), "wait": True})
    return c, src


def _mixed_client(monkeypatch, tmp_path):
    """A folder with two .jpg, a .png and a .svg, all indexed."""
    monkeypatch.setenv("PHOTA_HOME", str(tmp_path / "home"))
    src = tmp_path / "messy"; src.mkdir()
    make_jpeg(src / "a.jpg", captured="2025:08:07 08:00:00")
    make_jpeg(src / "b.jpg", captured="2025:08:07 09:00:00")
    make_png(src / "logo.png")
    make_svg(src / "icon.svg")
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


def test_by_format_groups_and_undo(monkeypatch, tmp_path):
    c, src = _mixed_client(monkeypatch, tmp_path)
    r = c.post("/api/organize", json={"action": "by_format"})
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "by_format"
    assert body["moved"] == 4
    assert sorted(body["folders"]) == ["JPEG", "PNG", "SVG"]
    assert (src / "JPEG" / "a.jpg").exists()
    assert (src / "JPEG" / "b.jpg").exists()
    assert (src / "PNG" / "logo.png").exists()
    assert (src / "SVG" / "icon.svg").exists()
    # Undo restores the originals.
    assert c.post("/api/undo").status_code == 200
    assert (src / "a.jpg").exists() and (src / "b.jpg").exists()
    assert (src / "logo.png").exists() and (src / "icon.svg").exists()
    assert not (src / "JPEG").exists()


def test_by_format_rerun_is_noop(monkeypatch, tmp_path):
    c, src = _mixed_client(monkeypatch, tmp_path)
    assert c.post("/api/organize", json={"action": "by_format"}).json()["moved"] == 4
    # Re-running: everything already lives in its label folder -> nothing moves,
    # no 409.
    r = c.post("/api/organize", json={"action": "by_format"})
    assert r.status_code == 200 and r.json()["moved"] == 0


def test_by_day_rerun_is_noop(monkeypatch, tmp_path):
    c, src = _client(monkeypatch, tmp_path, [
        ("a.jpg", {"captured": "2025:12:18 00:15:00"}),
        ("b.jpg", {"captured": "2025:12:25 00:15:00"}),
    ])
    assert c.post("/api/organize", json={"action": "by_day"}).json()["moved"] == 2
    r = c.post("/api/organize", json={"action": "by_day"})
    assert r.status_code == 200 and r.json()["moved"] == 0


def test_by_camera_rerun_is_noop(monkeypatch, tmp_path):
    c, src = _client(monkeypatch, tmp_path, [
        ("a.jpg", {"captured": "2025:12:18 00:15:00", "camera": "X-M5"}),
        ("b.jpg", {"captured": "2025:12:18 00:16:00", "camera": "EOS"}),
    ])
    assert c.post("/api/organize", json={"action": "by_camera"}).json()["moved"] == 2
    r = c.post("/api/organize", json={"action": "by_camera"})
    assert r.status_code == 200 and r.json()["moved"] == 0


def test_library_includes_format_counts(monkeypatch, tmp_path):
    c, src = _mixed_client(monkeypatch, tmp_path)
    body = c.get("/api/library").json()
    assert body["formats"] == {"JPEG": 2, "PNG": 1, "SVG": 1}
    # Existing fields preserved.
    assert body["count"] == 4
    assert "cameras" in body and "date_range" in body and "series" in body
