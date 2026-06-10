import numpy as np

from phota.preview import load_preview
from tests.fixtures import make_jpeg


def test_load_preview_returns_grayscale_array(photo_dir):
    p = make_jpeg(photo_dir / "a.jpg", sharp=True)
    arr = load_preview(str(p))
    assert isinstance(arr, np.ndarray)
    assert arr.ndim == 2  # grayscale
    assert max(arr.shape) <= 512


def test_load_preview_missing_file_returns_none():
    assert load_preview("/no/such/file.jpg") is None
