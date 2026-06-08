from pathlib import Path

import pytest

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


def test_undo_refuses_to_clobber_new_file_at_origin(tmp_path):
    # Sort a.jpg (content ORIGINAL_A) into a subfolder.
    a = tmp_path / 'a.jpg'
    a.write_text('ORIGINAL_A')
    organize.sort_into_folder(tmp_path, 'trip', [str(a)])
    sub = tmp_path / 'trip'
    assert (sub / 'a.jpg').read_text() == 'ORIGINAL_A'
    assert not a.exists()
    # A NEW file appears at the original location (re-import / new capture).
    a.write_text('NEW_A')
    # Undo must NOT silently destroy the new file.
    with pytest.raises(FileExistsError):
        organize.undo_last(tmp_path)
    # The new file is preserved, and the sorted original is left intact (no partial undo).
    assert a.read_text() == 'NEW_A'
    assert (sub / 'a.jpg').read_text() == 'ORIGINAL_A'


def test_undo_is_all_or_nothing_on_conflict(tmp_path):
    # Sort two files; only one origin gets re-occupied. The pre-pass must
    # abort the whole undo so the non-conflicting file is not half-restored.
    a = tmp_path / 'a.jpg'; b = tmp_path / 'b.jpg'
    a.write_text('ORIGINAL_A'); b.write_text('ORIGINAL_B')
    organize.sort_into_folder(tmp_path, 'trip', [str(a), str(b)])
    sub = tmp_path / 'trip'
    # Re-occupy only a.jpg at root.
    a.write_text('NEW_A')
    with pytest.raises(FileExistsError):
        organize.undo_last(tmp_path)
    # Nothing moved back: b.jpg is still in the subfolder (no partial undo).
    assert (sub / 'b.jpg').read_text() == 'ORIGINAL_B'
    assert not b.exists()
    assert a.read_text() == 'NEW_A'


def test_apply_order_undo_preserves_colliding_stripped_names(tmp_path):
    # Two files whose names strip to the same base ('a.jpg').
    f1 = tmp_path / '001_a.jpg'; f2 = tmp_path / '002_a.jpg'
    f1.write_text('001_a.jpg'); f2.write_text('002_a.jpg')
    # Swap their order; both still strip to 'a.jpg'.
    organize.apply_order(tmp_path, [str(f2), str(f1)])
    # After reorder: 001_a.jpg holds the old 002 content, 002_a.jpg holds old 001 content.
    assert (tmp_path / '001_a.jpg').read_text() == '002_a.jpg'
    assert (tmp_path / '002_a.jpg').read_text() == '001_a.jpg'
    # Undo must restore BOTH files with their original contents -- no clobber.
    organize.undo_last(tmp_path)
    assert (tmp_path / '001_a.jpg').read_text() == '001_a.jpg'
    assert (tmp_path / '002_a.jpg').read_text() == '002_a.jpg'
