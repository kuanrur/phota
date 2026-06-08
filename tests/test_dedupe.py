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


def test_group_keeper_is_sharpest(photo_dir):
    # a and b are pixel-identical duplicates; force b to be sharper than a.
    # The group must be ordered keeper-first (highest sharpness), so b leads.
    make_jpeg(photo_dir / 'a.jpg', captured='2025:12:18 00:15:00', sharp=True)
    make_jpeg(photo_dir / 'b.jpg', captured='2025:12:18 00:16:00', sharp=True)
    build_index(photo_dir)
    idx = Index()
    by_name = {p.filename: p for p in idx.all_photos()}
    idx.conn.execute(
        'UPDATE photos SET sharpness=? WHERE id=?', (5.0, by_name['a.jpg'].id)
    )
    idx.conn.execute(
        'UPDATE photos SET sharpness=? WHERE id=?', (99.0, by_name['b.jpg'].id)
    )
    idx.conn.commit()
    g = find_duplicate_groups(Index())[0]
    assert Index().get_photo(g[0]).filename == 'b.jpg'  # keeper = sharpest
    assert Index().get_photo(g[1]).filename == 'a.jpg'


def test_no_duplicates(photo_dir):
    make_jpeg(photo_dir / 'a.jpg', captured='2025:12:18 00:15:00', sharp=True)
    make_jpeg(photo_dir / 'c.jpg', captured='2025:12:18 00:17:00', sharp=False)
    build_index(photo_dir)
    assert find_duplicate_groups(Index()) == []


def test_exact_byte_duplicates_both_indexed_and_grouped(photo_dir):
    import shutil
    from phota.index import Index
    p = make_jpeg(photo_dir / 'a.jpg', captured='2025:12:18 00:15:00', sharp=True)
    shutil.copy2(p, photo_dir / 'a_copy.jpg')  # exact byte-for-byte copy
    build_index(photo_dir)
    photos = Index().all_photos()
    assert len(photos) == 2  # both files visible (not collapsed by content hash)
    groups = find_duplicate_groups(Index())
    assert len(groups) == 1 and set(groups[0]) == {p.id for p in photos}
