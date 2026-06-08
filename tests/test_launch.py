from typer.testing import CliRunner
from fastapi.testclient import TestClient
from phota.cli import app, launch
from phota.index import Index
from tests.fixtures import make_jpeg


def test_launch_builds_index_and_returns_app(photo_dir):
    make_jpeg(photo_dir / 'a.jpg', captured='2025:12:18 00:15:00')
    fastapi_app, folder = launch(str(photo_dir), open_browser=False, serve=False)
    assert len(Index().all_photos()) >= 1
    assert folder == str(photo_dir)
    c = TestClient(fastapi_app)
    assert c.get('/api/library').json()['count'] >= 1


def test_subcommands_still_present():
    out = CliRunner().invoke(app, ['--help']).stdout
    for cmd in ('scan', 'cull', 'organize', 'apply', 'open'):
        assert cmd in out
