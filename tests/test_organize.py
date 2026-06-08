from pathlib import Path

from phota import organize
from tests.fixtures import make_jpeg


def test_apply_order_renames_with_prefixes(tmp_path):
    a = make_jpeg(tmp_path / 'zebra.jpg'); b = make_jpeg(tmp_path / 'apple.jpg'); c = make_jpeg(tmp_path / 'mango.jpg')
    # desired order: apple, mango, zebra
    organize.apply_order(tmp_path, [str(b), str(c), str(a)])
    names = sorted(p.name for p in tmp_path.iterdir() if p.suffix == '.jpg')
    assert names == ['001_apple.jpg', '002_mango.jpg', '003_zebra.jpg']


def test_reorder_is_idempotent_on_prefixed_names(tmp_path):
    a = make_jpeg(tmp_path / 'a.jpg'); b = make_jpeg(tmp_path / 'b.jpg')
    organize.apply_order(tmp_path, [str(a), str(b)])
    p1 = tmp_path / '001_a.jpg'; p2 = tmp_path / '002_b.jpg'
    # reorder again, swapped, using the now-prefixed paths -> prefixes are stripped+reapplied
    organize.apply_order(tmp_path, [str(p2), str(p1)])
    names = sorted(p.name for p in tmp_path.iterdir() if p.suffix == '.jpg')
    assert names == ['001_b.jpg', '002_a.jpg']


def test_undo_restores_original_names(tmp_path):
    a = make_jpeg(tmp_path / 'a.jpg'); b = make_jpeg(tmp_path / 'b.jpg')
    organize.apply_order(tmp_path, [str(a), str(b)])
    organize.undo_last(tmp_path)
    names = sorted(p.name for p in tmp_path.iterdir() if p.suffix == '.jpg')
    assert names == ['a.jpg', 'b.jpg']


def test_sort_into_folder_moves_and_undo(tmp_path):
    a = make_jpeg(tmp_path / 'a.jpg'); b = make_jpeg(tmp_path / 'b.jpg'); make_jpeg(tmp_path / 'c.jpg')
    organize.sort_into_folder(tmp_path, 'Trip / 2025', [str(a), str(b)])
    sub = tmp_path / 'Trip  2025'  # slashes stripped by _safe_name
    assert (sub / 'a.jpg').exists() and (sub / 'b.jpg').exists()
    assert not (tmp_path / 'a.jpg').exists()  # moved out of root
    assert (tmp_path / 'c.jpg').exists()      # untouched
    organize.undo_last(tmp_path)
    assert (tmp_path / 'a.jpg').exists() and not (sub / 'a.jpg').exists()
