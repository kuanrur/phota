from phota.models import Photo
from phota.workflows import cull, organize, edit_list, find


def _p(pid, series, sharp, kind="jpeg", captured="2025-12-18T00:15:00", camera="X-T5"):
    return Photo(
        id=pid, path=f"/x/{pid}.jpg", filename=f"{pid}.jpg", kind=kind,
        series_id=series, sharpness=sharp, captured_at=captured, camera=camera,
    )


def test_cull_keeps_sharpest_per_series():
    photos = [
        _p("a", 0, 100.0),
        _p("b", 0, 500.0),  # sharpest in series 0
        _p("c", 1, 300.0),  # only one in series 1
    ]
    plan = cull(photos, out_dir="/out")
    kept = {op.photo_id for op in plan.ops}
    assert kept == {"b", "c"}


def test_organize_by_date_builds_dated_paths():
    photos = [_p("a", 0, 100.0, captured="2025-12-18T00:15:00")]
    plan = organize(photos, by="date", out_dir="/out")
    assert plan.ops[0].dst == "/out/2025-12-18/a.jpg"


def test_edit_list_picks_keeper_raws_only():
    photos = [
        _p("r", 0, 400.0, kind="raw"),
        _p("j", 0, 400.0, kind="jpeg"),
    ]
    plan = edit_list(photos, out_dir="/out")
    kinds = {op.photo_id for op in plan.ops}
    assert kinds == {"r"}  # only raw keepers go to the edit list


def test_find_filters_by_camera_and_date():
    photos = [
        _p("a", 0, 100.0, camera="X-T5", captured="2025-12-18T00:15:00"),
        _p("b", 0, 100.0, camera="EOS", captured="2025-03-21T00:00:00"),
    ]
    res = find(photos, camera="X-T5", after="2025-12-01")
    assert [p.id for p in res] == ["a"]
