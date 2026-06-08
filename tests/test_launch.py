import os

from typer.testing import CliRunner
from fastapi.testclient import TestClient
from phota.cli import app, launch
from phota.config import library_db_path
from phota.index import Index
from tests.fixtures import make_jpeg


def test_launch_builds_index_and_returns_app(photo_dir):
    make_jpeg(photo_dir / 'a.jpg', captured='2025:12:18 00:15:00')
    fastapi_app, folder = launch(str(photo_dir), open_browser=False, serve=False)
    assert len(Index().all_photos()) >= 1
    assert folder == str(photo_dir)
    c = TestClient(fastapi_app)
    assert c.get('/api/library').json()['count'] >= 1


def test_consecutive_launches_use_separate_per_folder_dbs(tmp_path, monkeypatch):
    """Different folders must never share state, even when launch() is called
    more than once in the same process. The launcher-owned PHOTA_DB must follow
    the folder it was last launched on."""
    # Simulate the real CLI: no external PHOTA_DB override in play.
    monkeypatch.delenv("PHOTA_DB", raising=False)
    monkeypatch.delenv("_PHOTA_DB_OWNER", raising=False)

    d1 = tmp_path / "folder1"
    d2 = tmp_path / "folder2"
    d1.mkdir()
    d2.mkdir()
    make_jpeg(d1 / "one.jpg", captured="2025:12:18 00:15:00")
    make_jpeg(d2 / "two.jpg", captured="2025:12:19 00:15:00")

    app1, _ = launch(str(d1), open_browser=False, serve=False)
    # After launching folder1, its per-folder db should be active.
    assert os.environ["PHOTA_DB"] == str(library_db_path(d1))
    lib1_after_first = TestClient(app1).get("/api/library").json()["count"]
    assert lib1_after_first == 1

    app2, _ = launch(str(d2), open_browser=False, serve=False)
    # Launching folder2 must switch to folder2's own per-folder db.
    assert os.environ["PHOTA_DB"] == str(library_db_path(d2))
    lib2 = TestClient(app2).get("/api/library").json()["count"]
    assert lib2 == 1

    # folder1's index must NOT have been clobbered/pruned by folder2's build.
    monkeypatch.setenv("PHOTA_DB", str(library_db_path(d1)))
    idx1 = Index()
    idx1.init_schema()
    names1 = {p.filename for p in idx1.all_photos()}
    assert names1 == {"one.jpg"}

    monkeypatch.setenv("PHOTA_DB", str(library_db_path(d2)))
    idx2 = Index()
    idx2.init_schema()
    names2 = {p.filename for p in idx2.all_photos()}
    assert names2 == {"two.jpg"}


def test_launch_respects_external_phota_db_override(photo_dir, monkeypatch):
    """A genuinely external PHOTA_DB (tests, power users) is respected and not
    overwritten by the launcher's per-folder path."""
    external = photo_dir.parent / "external.db"
    monkeypatch.setenv("PHOTA_DB", str(external))
    monkeypatch.delenv("_PHOTA_DB_OWNER", raising=False)
    make_jpeg(photo_dir / "a.jpg", captured="2025:12:18 00:15:00")

    launch(str(photo_dir), open_browser=False, serve=False)
    assert os.environ["PHOTA_DB"] == str(external)


def test_subcommands_still_present():
    out = CliRunner().invoke(app, ['--help']).stdout
    for cmd in ('scan', 'cull', 'organize', 'apply', 'open'):
        assert cmd in out
