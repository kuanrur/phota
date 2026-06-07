from phota.index import Index
from phota.models import Photo


def test_upsert_and_get():
    idx = Index()
    idx.init_schema()
    p = Photo(id="abc", path="/x/a.jpg", filename="a.jpg", kind="jpeg", size=10)
    idx.upsert_photo(p)
    got = idx.get_photo("abc")
    assert got.filename == "a.jpg"
    assert got.size == 10


def test_upsert_is_idempotent_and_updates():
    idx = Index()
    idx.init_schema()
    idx.upsert_photo(Photo(id="abc", path="/x/a.jpg", filename="a.jpg", kind="jpeg"))
    idx.upsert_photo(Photo(id="abc", path="/x/a.jpg", filename="a.jpg", kind="jpeg", sharpness=9.0))
    assert idx.get_photo("abc").sharpness == 9.0
    assert len(idx.all_photos()) == 1


def test_known_ids_for_incremental_scan():
    idx = Index()
    idx.init_schema()
    idx.upsert_photo(Photo(id="abc", path="/x/a.jpg", filename="a.jpg", kind="jpeg", mtime=5.0))
    known = idx.known_mtimes()
    assert known == {"abc": 5.0}
