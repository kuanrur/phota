import phota.ai as ai
from phota.models import Photo


def _p(pid, sharp, series=0):
    return Photo(id=pid, path=f"/x/{pid}.jpg", filename=f"{pid}.jpg",
                 kind="jpeg", series_id=series, sharpness=sharp)


def test_rank_with_ai_uses_provider_and_caches(monkeypatch):
    calls = []

    def fake_analyze(path):
        calls.append(path)
        return {"caption": "a cat", "tags": ["cat"], "subjects": ["cat"],
                "aesthetic_score": 0.9}

    monkeypatch.setattr(ai, "_analyze_image", fake_analyze)
    monkeypatch.setattr(ai, "_HAS_KEY", True)
    photos = [_p("a", 100.0), _p("b", 100.0)]
    ranked = ai.rank_with_ai(photos)
    assert all(hasattr(p, "_aesthetic") for p in ranked)
    ai.rank_with_ai(photos)
    assert len(calls) == 2  # one per distinct photo, cached second time


def test_semantic_match_filters_by_tags(monkeypatch):
    def fake_analyze(path):
        return {"caption": "sunset over water", "tags": ["sunset", "water"],
                "subjects": ["sky"], "aesthetic_score": 0.5}

    monkeypatch.setattr(ai, "_analyze_image", fake_analyze)
    monkeypatch.setattr(ai, "_HAS_KEY", True)
    photos = [_p("a", 100.0)]
    ids = ai.semantic_match(photos, "sunset")
    assert ids == {"a"}


def test_no_api_key_degrades(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(ai, "_HAS_KEY", False)
    photos = [_p("a", 100.0)]
    assert ai.rank_with_ai(photos) == photos
    assert ai.semantic_match(photos, "anything") is None
