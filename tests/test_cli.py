from typer.testing import CliRunner

from phota.cli import app
from tests.fixtures import make_jpeg

runner = CliRunner()


def test_scan_then_status(photo_dir):
    make_jpeg(photo_dir / "a.jpg", captured="2025:12:18 00:15:00", camera="X-T5")
    r = runner.invoke(app, ["scan", str(photo_dir)])
    assert r.exit_code == 0
    assert "analyzed" in r.stdout.lower()
    r2 = runner.invoke(app, ["status"])
    assert r2.exit_code == 0
    assert "photos" in r2.stdout.lower()


def test_cull_writes_plan_without_touching_originals(photo_dir, tmp_path):
    make_jpeg(photo_dir / "a.jpg", captured="2025:12:18 00:15:00", sharp=True)
    make_jpeg(photo_dir / "b.jpg", captured="2025:12:18 00:15:01", sharp=False)
    runner.invoke(app, ["scan", str(photo_dir)])
    plan_path = tmp_path / "cull.json"
    r = runner.invoke(app, ["cull", "--plan", str(plan_path)])
    assert r.exit_code == 0
    assert plan_path.exists()
    assert (photo_dir / "a.jpg").exists()
    assert (photo_dir / "b.jpg").exists()


def test_apply_copies_into_output(photo_dir, tmp_path):
    make_jpeg(photo_dir / "a.jpg", captured="2025:12:18 00:15:00", sharp=True)
    runner.invoke(app, ["scan", str(photo_dir)])
    plan_path = tmp_path / "cull.json"
    runner.invoke(app, ["cull", "--plan", str(plan_path), "--out", str(tmp_path / "out")])
    r = runner.invoke(app, ["apply", str(plan_path), "--yes"])
    assert r.exit_code == 0
    assert (tmp_path / "out" / "a.jpg").exists()
