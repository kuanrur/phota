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


def test_sort_partial_failure_persists_manifest_and_undo_recovers(tmp_path):
    # The selection has unique basenames (passes pre-validation) but a foreign
    # file already occupies dest/b.jpg. a.jpg is moved first, then b.jpg raises
    # FileExistsError mid-loop. The manifest of the completed move (a.jpg) MUST
    # still be written so undo can recover the stranded file.
    a = tmp_path / 'a.jpg'; b = tmp_path / 'b.jpg'
    a.write_text('ORIG_A'); b.write_text('ORIG_B')
    dest = tmp_path / 'trip'
    dest.mkdir()
    (dest / 'b.jpg').write_text('FOREIGN_B')  # pre-occupies the second target
    with pytest.raises(FileExistsError):
        organize.sort_into_folder(tmp_path, 'trip', [str(a), str(b)])
    # a.jpg was moved into dest; the manifest recorded it so undo can recover it.
    assert (dest / 'a.jpg').read_text() == 'ORIG_A'
    assert not a.exists()
    # The foreign file at dest/b.jpg is untouched; b.jpg never moved.
    assert (dest / 'b.jpg').read_text() == 'FOREIGN_B'
    assert b.read_text() == 'ORIG_B'
    restored = organize.undo_last(tmp_path)
    assert restored == 1
    assert a.read_text() == 'ORIG_A'
    assert not (dest / 'a.jpg').exists()


def test_sort_rejects_duplicate_basenames_with_zero_mutation(tmp_path):
    # Two selected photos share a basename (e.g. two IMG_0001.jpg from different
    # subdirs). sort_into_folder must pre-validate and reject with NO filesystem
    # mutation: no dest subfolder created, no file moved, no manifest written.
    s1 = tmp_path / 's1'; s2 = tmp_path / 's2'
    s1.mkdir(); s2.mkdir()
    f1 = s1 / 'x.jpg'; f2 = s2 / 'x.jpg'
    f1.write_text('FROM_S1'); f2.write_text('FROM_S2')
    with pytest.raises(FileExistsError):
        organize.sort_into_folder(tmp_path, 'trip', [str(f1), str(f2)])
    # Nothing moved, no subfolder, no manifest.
    assert f1.read_text() == 'FROM_S1'
    assert f2.read_text() == 'FROM_S2'
    assert not (tmp_path / 'trip').exists()
    assert not organize.manifest_path(tmp_path).exists()


def test_sort_rejects_duplicate_id_in_selection_with_zero_mutation(tmp_path):
    # The UI sending the same path twice (duplicate id) is also a basename
    # collision and must be rejected before any move.
    a = tmp_path / 'a.jpg'
    a.write_text('A')
    with pytest.raises(FileExistsError):
        organize.sort_into_folder(tmp_path, 'trip', [str(a), str(a)])
    assert a.read_text() == 'A'
    assert not (tmp_path / 'trip').exists()
    assert not organize.manifest_path(tmp_path).exists()


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


def test_apply_order_refuses_to_overwrite_foreign_final_target(tmp_path):
    # A pre-existing file already occupies the final NNN_ slot that the
    # reordered file would land on. Reordering must NOT clobber it.
    keep = tmp_path / '001_a.jpg'; mover = tmp_path / '002_a.jpg'
    keep.write_text('FIRST A - keep me'); mover.write_text('SECOND A')
    # Reorder just 002_a.jpg to position 1 -> final name strips to a.jpg ->
    # re-prefixes to 001_a.jpg, which already exists as a foreign file.
    with pytest.raises(FileExistsError):
        organize.apply_order(tmp_path, [str(mover)])
    # Both files survive with their original contents; the folder is untouched.
    assert keep.read_text() == 'FIRST A - keep me'
    assert mover.read_text() == 'SECOND A'
    # No temp files left stranded, no manifest written.
    assert sorted(p.name for p in tmp_path.iterdir()) == ['001_a.jpg', '002_a.jpg']


def test_apply_order_rolls_back_on_missing_path(tmp_path):
    # A path in the middle of the list is missing. apply_order must roll back
    # already-moved files and leave the folder exactly as it was, no manifest.
    a = make_jpeg(tmp_path / 'a.jpg'); b = make_jpeg(tmp_path / 'b.jpg')
    missing = tmp_path / 'missing.jpg'
    with pytest.raises(FileNotFoundError):
        organize.apply_order(tmp_path, [str(a), str(missing), str(b)])
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ['a.jpg', 'b.jpg']  # no .phota_tmp_* leftovers, no manifest


def test_apply_order_keeps_subfolder_files_in_place_and_undo_round_trips(tmp_path):
    # A photo nested in a subfolder must be prefixed in place (in its own
    # directory), not relocated up into the parent. Undo must round-trip it
    # back to the subfolder, leaving the subfolder populated.
    sub = tmp_path / 'sub'; sub.mkdir()
    x = sub / 'x.jpg'; x.write_text('X')
    organize.apply_order(tmp_path, [str(x)])
    assert (sub / '001_x.jpg').read_text() == 'X'
    assert not (tmp_path / '001_x.jpg').exists()  # not moved up to parent
    organize.undo_last(tmp_path)
    assert (sub / 'x.jpg').read_text() == 'X'     # restored to the subfolder
    assert not (tmp_path / 'x.jpg').exists()
