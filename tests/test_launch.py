import os

from typer.testing import CliRunner
from fastapi.testclient import TestClient
from phota.cli import app, launch
from phota.config import library_db_path
from phota.index import Index
from tests.fixtures import make_jpeg


def test_launch_builds_index_and_returns_app(photo_dir):
    make_jpeg(photo_dir / 'a.jpg', captured='2025:12:18 00:15:00')
    # launch() no longer pre-indexes; the UI triggers indexing via open-folder.
    fastapi_app, folder = launch(str(photo_dir), open_browser=False, serve=False)
    assert folder == str(photo_dir)
    c = TestClient(fastapi_app)
    r = c.post('/api/open-folder', json={'path': str(photo_dir), 'wait': True})
    assert r.status_code == 200
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
    c1 = TestClient(app1)
    c1.post("/api/open-folder", json={"path": str(d1), "wait": True})
    lib1_after_first = c1.get("/api/library").json()["count"]
    assert lib1_after_first == 1

    app2, _ = launch(str(d2), open_browser=False, serve=False)
    # Launching folder2 must switch to folder2's own per-folder db.
    assert os.environ["PHOTA_DB"] == str(library_db_path(d2))
    c2 = TestClient(app2)
    c2.post("/api/open-folder", json={"path": str(d2), "wait": True})
    lib2 = c2.get("/api/library").json()["count"]
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


def test_main_opens_directory_arg(monkeypatch, photo_dir):
    import sys, os
    import phota.cli as cli
    seen = {}
    monkeypatch.setattr(cli, 'launch', lambda folder=None, **kw: seen.update(folder=folder))
    monkeypatch.setattr(sys, 'argv', ['phota', str(photo_dir)])
    cli.main()
    assert seen['folder'] == os.path.abspath(str(photo_dir))


def test_main_no_args_opens_picker(monkeypatch, tmp_path):
    # bare `phota` launches with no folder so the controller shows the
    # Finder-folder picker (folder=None), rather than defaulting to cwd.
    import sys
    import phota.cli as cli
    seen = {}
    monkeypatch.setattr(cli, 'launch', lambda folder=None, **kw: seen.update(folder=folder, called=True))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['phota'])
    cli.main()
    assert seen['called'] is True and seen['folder'] is None


def test_main_delegates_subcommands(monkeypatch):
    import sys
    import phota.cli as cli
    seen = {}
    monkeypatch.setattr(cli, 'app', lambda: seen.update(app=True))
    monkeypatch.setattr(sys, 'argv', ['phota', 'status'])
    cli.main()
    assert seen.get('app') is True


def test_open_app_window_builds_app_command(monkeypatch):
    import sys, subprocess, os
    import phota.cli as cli
    if sys.platform != 'darwin':
        return
    captured = {}
    monkeypatch.setattr(os.path, 'exists', lambda p: True)
    monkeypatch.setattr(subprocess, 'Popen', lambda args, **kw: captured.setdefault('args', list(args)))
    cli.open_app_window('http://127.0.0.1:9999')  # must not raise (regression: Path import)
    assert '--app=http://127.0.0.1:9999' in captured['args']
