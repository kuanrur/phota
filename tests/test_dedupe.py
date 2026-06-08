from phota.dedupe import find_duplicate_groups
from phota.engine import build_index
from phota.index import Index
from tests.fixtures import make_jpeg


def test_groups_identical_photos(photo_dir):
    # a and b are pixel-identical (same sharp checkerboard) -> same phash -> duplicates
    make_jpeg(photo_dir / 'a.jpg', captured='2025:12:18 00:15:00', sharp=True)
    make_jpeg(photo_dir / 'b.jpg', captured='2025:12:18 00:16:00', sharp=True)
    make_jpeg(photo_dir / 'c.jpg', captured='2025:12:18 00:17:00', sharp=False)  # different
    build_index(photo_dir)
    groups = find_duplicate_groups(Index())
    assert len(groups) == 1
    flat = {pid for g in groups for pid in g}
    ids = {p.id: p.filename for p in Index().all_photos()}
    names = {ids[pid] for pid in groups[0]}
    assert names == {'a.jpg', 'b.jpg'}


def test_no_duplicates(photo_dir):
    make_jpeg(photo_dir / 'a.jpg', captured='2025:12:18 00:15:00', sharp=True)
    make_jpeg(photo_dir / 'c.jpg', captured='2025:12:18 00:17:00', sharp=False)
    build_index(photo_dir)
    assert find_duplicate_groups(Index()) == []
