from typer.testing import CliRunner

from phota.cli import app
from tests.fixtures import make_jpeg

runner = CliRunner()


def test_full_flow_scan_cull_apply(photo_dir, tmp_path):
    # a 3-shot burst + a separate frame
    make_jpeg(photo_dir / "a.jpg", captured="2025:12:18 00:15:00", sharp=False)
    make_jpeg(photo_dir / "b.jpg", captured="2025:12:18 00:15:01", sharp=True)
    make_jpeg(photo_dir / "c.jpg", captured="2025:12:18 00:15:02", sharp=False)
    make_jpeg(photo_dir / "d.jpg", captured="2025:12:18 09:00:00", sharp=True)

    assert runner.invoke(app, ["scan", str(photo_dir)]).exit_code == 0
    plan_path = tmp_path / "cull.json"
    out_dir = tmp_path / "out"
    runner.invoke(app, ["cull", "--plan", str(plan_path), "--out", str(out_dir)])
    r = runner.invoke(app, ["apply", str(plan_path), "--yes"])
    assert r.exit_code == 0
    # series 1 keeper is the sharp b.jpg; series 2 is d.jpg
    assert (out_dir / "b.jpg").exists()
    assert (out_dir / "d.jpg").exists()
    assert not (out_dir / "a.jpg").exists()
