from phota.grouping import assign_series, assign_events, find_raw_jpeg_pairs
from phota.models import Photo


def _p(pid, captured, kind="jpeg", filename=None):
    return Photo(
        id=pid,
        path=f"/x/{pid}",
        filename=filename or f"{pid}.jpg",
        kind=kind,
        captured_at=captured,
    )


def test_assign_series_groups_close_timestamps():
    photos = [
        _p("a", "2025-12-18T00:15:00"),
        _p("b", "2025-12-18T00:15:01"),
        _p("c", "2025-12-18T00:15:02"),
        _p("d", "2025-12-18T00:20:00"),  # >3s gap -> new series
    ]
    assign_series(photos)
    assert photos[0].series_id == photos[1].series_id == photos[2].series_id
    assert photos[3].series_id != photos[0].series_id


def test_assign_events_splits_on_large_gaps():
    photos = [
        _p("a", "2025-12-18T00:15:00"),
        _p("b", "2025-12-18T00:20:00"),  # same event
        _p("c", "2025-12-18T08:00:00"),  # >3h gap -> new event
    ]
    events = assign_events(photos)
    assert events["a"] == events["b"]
    assert events["c"] != events["a"]


def test_find_raw_jpeg_pairs_matches_basename():
    photos = [
        _p("r1", "2025-03-21T10:00:00", kind="raw", filename="IMG_1936.CR3"),
        _p("j1", "2025-03-21T10:00:00", kind="jpeg", filename="IMG_1936.jpeg"),
        _p("x", "2025-03-21T11:00:00", kind="jpeg", filename="DSCF1.jpg"),
    ]
    pairs = find_raw_jpeg_pairs(photos)
    assert ("r1", "j1") in pairs
    assert len(pairs) == 1
