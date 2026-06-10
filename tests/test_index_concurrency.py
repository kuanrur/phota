"""Mutating endpoints must not run build_index while a background index job
is in progress on the same db. Two concurrent build_index passes both prune()
and rewrite series_id, contending on sqlite (database is locked) and
interleaving each other's deletes/grouping. They must return 409 instead.
"""
import pytest
from fastapi.testclient import TestClient

from phota.server import create_app
from tests.fixtures import make_jpeg


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv("PHOTA_HOME", str(tmp_path / "home"))
    src = tmp_path / "messy"
    src.mkdir()
    make_jpeg(src / "a.jpg", captured="2025:12:18 00:15:00")
    make_jpeg(src / "b.jpg", captured="2025:12:18 00:16:00")
    c = TestClient(create_app(None))
    c.post("/api/open-folder", json={"path": str(src), "wait": True})
    return c, src


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("post", "/api/sort", {"folder_name": "x", "ids": []}),
        ("post", "/api/reorder", {"ordered_ids": []}),
        ("post", "/api/undo", {}),
        ("post", "/api/organize", {"action": "sort_by_date"}),
    ],
)
def test_mutating_endpoint_409_while_indexing(monkeypatch, tmp_path, method, path, body):
    c, src = _client(monkeypatch, tmp_path)
    # Simulate a background indexer still writing the same db.
    c.app.state.index_job["running"] = True
    r = getattr(c, method)(path, json=body)
    assert r.status_code == 409, (path, r.status_code, r.text)
