from phota.quality import score_photo
from tests.fixtures import make_jpeg


def test_sharp_scores_higher_than_blurred(photo_dir):
    sharp = make_jpeg(photo_dir / "sharp.jpg", sharp=True)
    blurred = make_jpeg(photo_dir / "blur.jpg", sharp=False)
    s = score_photo(str(sharp))
    b = score_photo(str(blurred))
    assert s["sharpness"] > b["sharpness"]


def test_score_includes_exposure_and_phash(photo_dir):
    p = make_jpeg(photo_dir / "a.jpg", sharp=True)
    out = score_photo(str(p))
    assert "exposure_score" in out
    assert isinstance(out["phash"], str) and out["phash"]


def test_score_unreadable_returns_none_fields():
    out = score_photo("/no/such.jpg")
    assert out["sharpness"] is None
    assert out["phash"] is None
