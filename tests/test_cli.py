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


def test_apply_move_writes_manifest_and_undo_restores(photo_dir, tmp_path):
    make_jpeg(photo_dir / "a.jpg", captured="2025:12:18 00:15:00", sharp=True)
    runner.invoke(app, ["scan", str(photo_dir)])
    plan_path = tmp_path / "cull.json"
    out_dir = tmp_path / "out"
    runner.invoke(app, ["cull", "--plan", str(plan_path), "--out", str(out_dir)])
    r = runner.invoke(app, ["apply", str(plan_path), "--move", "--yes"])
    assert r.exit_code == 0
    moved = out_dir / "a.jpg"
    assert moved.exists()
    assert not (photo_dir / "a.jpg").exists()  # original moved away
    manifest_path = str(plan_path) + ".manifest.json"
    import os
    assert os.path.exists(manifest_path)
    r2 = runner.invoke(app, ["undo", manifest_path])
    assert r2.exit_code == 0
    assert (photo_dir / "a.jpg").exists()  # restored
    assert not moved.exists()


def test_find_semantic_without_key_degrades(photo_dir, monkeypatch):
    make_jpeg(photo_dir / "a.jpg", captured="2025:12:18 00:15:00", camera="X-T5")
    runner.invoke(app, ["scan", str(photo_dir)])
    import phota.ai as ai
    monkeypatch.setattr(ai, "_HAS_KEY", False)
    r = runner.invoke(app, ["find", "sunset"])
    assert r.exit_code == 0
    assert "unavailable" in r.stdout.lower()
    assert "a.jpg" not in r.stdout  # did NOT dump all photos
