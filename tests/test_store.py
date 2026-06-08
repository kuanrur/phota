from phota import store
from phota.index import Index
from phota.models import Photo


def _seed(idx, pid):
    idx.upsert_photo(Photo(id=pid, path=f'/x/{pid}.jpg', filename=f'{pid}.jpg', kind='jpeg'))


def test_keep_flag_roundtrip():
    idx = Index(); idx.init_schema()
    _seed(idx, 'a')
    assert store.get_keep(idx, 'a') is None
    store.set_keep(idx, 'a', True)
    assert store.get_keep(idx, 'a') is True
    store.set_keep(idx, 'a', False)
    assert store.get_keep(idx, 'a') is False
    store.set_keep(idx, 'a', None)
    assert store.get_keep(idx, 'a') is None


def test_album_crud_and_membership():
    idx = Index(); idx.init_schema()
    for p in ('a', 'b', 'c'):
        _seed(idx, p)
    store.create_album(idx, 'Iceland')
    assert [a['name'] for a in store.list_albums(idx)] == ['Iceland']
    store.add_to_album(idx, 'Iceland', ['a', 'b'])
    store.add_to_album(idx, 'Iceland', ['a'])  # idempotent
    assert sorted(store.photos_in_album(idx, 'Iceland')) == ['a', 'b']
    assert store.list_albums(idx)[0]['count'] == 2
    assert store.albums_for(idx, 'a') == ['Iceland']
    store.remove_from_album(idx, 'Iceland', ['a'])
    assert store.photos_in_album(idx, 'Iceland') == ['b']
    store.delete_album(idx, 'Iceland')
    assert store.list_albums(idx) == []


def test_existing_photo_roundtrip_still_works():
    idx = Index(); idx.init_schema()
    _seed(idx, 'z')
    assert idx.get_photo('z').filename == 'z.jpg'
