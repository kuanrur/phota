import phota.ai as ai
from phota.index import Index
from phota.models import Photo


class FakeProvider:
    vision = True

    def __init__(self, result=None):
        self.calls = 0
        self.result = result or {'caption': 'a cat', 'tags': ['cat'], 'subjects': ['cat'], 'aesthetic_score': 0.9}

    def available(self):
        return True

    def analyze_image(self, path):
        self.calls += 1
        return self.result


def _photo(pid):
    return Photo(id=pid, path=f'/x/{pid}.jpg', filename=f'{pid}.jpg', kind='jpeg', sharpness=100.0, series_id=0)


def test_analyze_caches(monkeypatch):
    fake = FakeProvider()
    monkeypatch.setattr(ai, '_provider', lambda: fake)
    idx = Index(); idx.init_schema(); idx.upsert_photo(_photo('a'))
    p = idx.get_photo('a')
    assert ai.analyze(idx, p)['caption'] == 'a cat'
    ai.analyze(idx, p)
    assert fake.calls == 1  # second call served from cache


def test_no_provider_degrades(monkeypatch):
    monkeypatch.setattr(ai, '_provider', lambda: None)
    idx = Index(); idx.init_schema()
    photos = [_photo('a')]
    assert ai.rank_with_ai(photos) == photos
    assert ai.semantic_match(photos, 'x') is None
    assert ai.search(idx, 'x') is None


def test_rank_with_ai_sets_aesthetic(monkeypatch):
    monkeypatch.setattr(ai, '_provider', lambda: FakeProvider())
    idx = Index(); idx.init_schema(); idx.upsert_photo(_photo('a'))
    ranked = ai.rank_with_ai([idx.get_photo('a')])
    assert ranked[0]._aesthetic == 0.9


def test_semantic_match_filters(monkeypatch):
    monkeypatch.setattr(ai, '_provider', lambda: FakeProvider({'caption': 'sunset', 'tags': ['sunset'], 'subjects': [], 'aesthetic_score': 0.5}))
    idx = Index(); idx.init_schema(); idx.upsert_photo(_photo('a'))
    assert ai.semantic_match([idx.get_photo('a')], 'sunset') == {'a'}
