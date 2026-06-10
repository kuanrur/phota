from phota.engine import build_index
from phota.index import Index
from tests.fixtures import make_jpeg


def test_build_index_populates_all_fields(photo_dir):
    make_jpeg(photo_dir / "a.jpg", captured="2025:12:18 00:15:00", camera="X-T5", sharp=True)
    make_jpeg(photo_dir / "b.jpg", captured="2025:12:18 00:15:01", camera="X-T5", sharp=False)
    stats = build_index(photo_dir)
    assert stats["scanned"] == 2
    assert stats["analyzed"] == 2
    idx = Index()
    photos = idx.all_photos()
    assert all(p.sharpness is not None for p in photos)
    assert all(p.captured_at is not None for p in photos)
    assert all(p.series_id is not None for p in photos)


def test_build_index_is_incremental(photo_dir):
    make_jpeg(photo_dir / "a.jpg", captured="2025:12:18 00:15:00")
    build_index(photo_dir)
    make_jpeg(photo_dir / "b.jpg", captured="2025:12:18 00:15:30")
    stats = build_index(photo_dir)
    # only the new file is analyzed the second time
    assert stats["analyzed"] == 1
    assert stats["scanned"] == 2


def test_deleted_file_is_pruned(photo_dir):
    from phota.index import Index
    make_jpeg(photo_dir / "a.jpg", captured="2025:12:18 00:15:00")
    make_jpeg(photo_dir / "b.jpg", captured="2025:12:18 00:15:30")
    build_index(photo_dir)
    (photo_dir / "b.jpg").unlink()
    stats = build_index(photo_dir)
    assert stats["pruned"] == 1
    ids_left = {p.filename for p in Index().all_photos()}
    assert ids_left == {"a.jpg"}


def test_pairs_cleared_when_no_pairs_remain(photo_dir):
    from phota.index import Index
    # seed a stale pair, then rebuild over a dir that has no raw/jpeg pair
    make_jpeg(photo_dir / "a.jpg", captured="2025:12:18 00:15:00")
    build_index(photo_dir)
    idx = Index()
    idx.add_pair("ghost_raw", "ghost_jpeg")
    build_index(photo_dir)
    assert Index().all_pairs() == []
