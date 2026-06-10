from fastapi.testclient import TestClient
import phota.server as server
from phota.server import create_app


def _capture(monkeypatch, returns=("", None)):
    """Monkeypatch _run_osascript to record scripts and return a canned result.

    `returns` may be a single (stdout, error) tuple applied to every call, or a
    list of tuples consumed in order.
    """
    calls = []

    def fake(script):
        calls.append(script)
        if isinstance(returns, list):
            return returns[len(calls) - 1] if len(calls) <= len(returns) else ("", None)
        return returns

    monkeypatch.setattr(server, "_run_osascript", fake)
    return calls


def test_cleanup_runs_clean_up_for_active_folder(monkeypatch, tmp_path):
    folder = tmp_path / "shoot"
    folder.mkdir()
    calls = _capture(monkeypatch, returns=("ok", None))
    c = TestClient(create_app(str(folder)))
    r = c.post("/api/finder-tidy", json={"action": "cleanup"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    joined = "\n".join(calls)
    assert "clean up" in joined
    assert str(folder) in joined


def test_cleanup_no_active_folder_returns_400(monkeypatch):
    _capture(monkeypatch, returns=("ok", None))
    c = TestClient(create_app(None))
    r = c.post("/api/finder-tidy", json={"action": "cleanup"})
    assert r.status_code == 400


def test_cleanup_no_window_returns_error(monkeypatch, tmp_path):
    folder = tmp_path / "shoot"
    folder.mkdir()
    _capture(monkeypatch, returns=("no-window", None))
    c = TestClient(create_app(str(folder)))
    r = c.post("/api/finder-tidy", json={"action": "cleanup"})
    assert r.status_code == 200
    assert r.json() == {"ok": False, "error": "no-window"}


def test_cleanup_permission_error_propagates(monkeypatch, tmp_path):
    folder = tmp_path / "shoot"
    folder.mkdir()
    _capture(monkeypatch, returns=("", "permission"))
    c = TestClient(create_app(str(folder)))
    r = c.post("/api/finder-tidy", json={"action": "cleanup"})
    assert r.status_code == 200
    assert r.json() == {"ok": False, "error": "permission"}


def test_keep_on_script_arranges_by_name(monkeypatch, tmp_path):
    folder = tmp_path / "shoot"
    folder.mkdir()
    calls = _capture(monkeypatch, returns=("ok", None))
    c = TestClient(create_app(str(folder)))
    r = c.post("/api/finder-tidy", json={"action": "keep_on"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    joined = "\n".join(calls)
    assert "arranged by name" in joined
    assert str(folder) in joined


def test_keep_off_script_not_arranged(monkeypatch, tmp_path):
    folder = tmp_path / "shoot"
    folder.mkdir()
    calls = _capture(monkeypatch, returns=("ok", None))
    c = TestClient(create_app(str(folder)))
    r = c.post("/api/finder-tidy", json={"action": "keep_off"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    joined = "\n".join(calls)
    assert "not arranged" in joined
    assert str(folder) in joined


def test_keep_no_active_folder_returns_400(monkeypatch):
    _capture(monkeypatch, returns=("ok", None))
    c = TestClient(create_app(None))
    r = c.post("/api/finder-tidy", json={"action": "keep_on"})
    assert r.status_code == 400


def test_keep_permission_error_propagates(monkeypatch, tmp_path):
    folder = tmp_path / "shoot"
    folder.mkdir()
    _capture(monkeypatch, returns=("", "permission"))
    c = TestClient(create_app(str(folder)))
    r = c.post("/api/finder-tidy", json={"action": "keep_on"})
    assert r.status_code == 200
    assert r.json() == {"ok": False, "error": "permission"}


def test_get_maps_arranged_true(monkeypatch, tmp_path):
    folder = tmp_path / "shoot"
    folder.mkdir()
    _capture(monkeypatch, returns=("arranged by name", None))
    c = TestClient(create_app(str(folder)))
    r = c.get("/api/finder-tidy")
    assert r.status_code == 200
    assert r.json() == {"arranged": True}


def test_get_maps_snap_to_grid_true(monkeypatch, tmp_path):
    folder = tmp_path / "shoot"
    folder.mkdir()
    _capture(monkeypatch, returns=("snap to grid", None))
    c = TestClient(create_app(str(folder)))
    r = c.get("/api/finder-tidy")
    assert r.status_code == 200
    assert r.json() == {"arranged": True}


def test_get_maps_not_arranged_false(monkeypatch, tmp_path):
    folder = tmp_path / "shoot"
    folder.mkdir()
    _capture(monkeypatch, returns=("not arranged", None))
    c = TestClient(create_app(str(folder)))
    r = c.get("/api/finder-tidy")
    assert r.status_code == 200
    assert r.json() == {"arranged": False}


def test_get_maps_unknown_null(monkeypatch, tmp_path):
    folder = tmp_path / "shoot"
    folder.mkdir()
    _capture(monkeypatch, returns=("", None))
    c = TestClient(create_app(str(folder)))
    r = c.get("/api/finder-tidy")
    assert r.status_code == 200
    assert r.json() == {"arranged": None}


def test_get_no_active_folder_returns_400(monkeypatch):
    _capture(monkeypatch, returns=("not arranged", None))
    c = TestClient(create_app(None))
    r = c.get("/api/finder-tidy")
    assert r.status_code == 400


def test_get_permission_error_returns_null(monkeypatch, tmp_path):
    folder = tmp_path / "shoot"
    folder.mkdir()
    _capture(monkeypatch, returns=("", "permission"))
    c = TestClient(create_app(str(folder)))
    r = c.get("/api/finder-tidy")
    assert r.status_code == 200
    assert r.json() == {"arranged": None, "error": "permission"}
