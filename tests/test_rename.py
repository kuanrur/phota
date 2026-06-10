from dataclasses import dataclass

import pytest

from phota import organize
from phota.config import format_label
from phota.rename import plan_renames, safe_word


@dataclass
class _P:
    path: str
    filename: str
    captured_at: str | None


def _photo(path, captured_at):
    from pathlib import Path

    return _P(path=path, filename=Path(path).name, captured_at=captured_at)


# ---------------------------------------------------------------------------
# plan_renames -- pure name planning
# ---------------------------------------------------------------------------

def test_plan_number_zero_padded_sorted_by_capture(tmp_path):
    a = _photo(str(tmp_path / "z.jpg"), "2025-08-07T09:00:00")
    b = _photo(str(tmp_path / "a.jpg"), "2025-08-07T08:00:00")
    plan = plan_renames([a, b], "number")
    # sorted by capture: b (08:00) first, then a (09:00)
    assert plan == [
        (str(tmp_path / "a.jpg"), "001.jpg"),
        (str(tmp_path / "z.jpg"), "002.jpg"),
    ]


def test_plan_number_padding_grows_with_total(tmp_path):
    photos = [
        _photo(str(tmp_path / f"f{i}.jpg"), f"2025-08-07T08:{i:02d}:00")
        for i in range(1000)
    ]
    plan = plan_renames(photos, "number")
    assert plan[0][1] == "0001.jpg"  # pad = len("1000") = 4
    assert plan[-1][1] == "1000.jpg"


def test_plan_date_number_counter_resets_per_day(tmp_path):
    photos = [
        _photo(str(tmp_path / "a.jpg"), "2025-08-07T08:00:00"),
        _photo(str(tmp_path / "b.jpg"), "2025-08-07T09:00:00"),
        _photo(str(tmp_path / "c.jpg"), "2025-08-08T08:00:00"),
    ]
    plan = plan_renames(photos, "date_number")
    assert plan == [
        (str(tmp_path / "a.jpg"), "2025-08-07_01.jpg"),
        (str(tmp_path / "b.jpg"), "2025-08-07_02.jpg"),
        (str(tmp_path / "c.jpg"), "2025-08-08_01.jpg"),
    ]


def test_plan_date_number_padding_per_day(tmp_path):
    # A day with 10+ photos pads to 2 (max(2, digits)). A day with 100+ pads 3.
    big = [
        _photo(str(tmp_path / f"x{i}.jpg"), f"2025-08-07T08:{i:02d}:00")
        for i in range(100)
    ]
    plan = plan_renames(big, "date_number")
    assert plan[0][1] == "2025-08-07_001.jpg"
    assert plan[-1][1] == "2025-08-07_100.jpg"


def test_plan_datetime_basic(tmp_path):
    a = _photo(str(tmp_path / "a.jpg"), "2025-08-07T14:30:52")
    plan = plan_renames([a], "datetime")
    assert plan == [(str(tmp_path / "a.jpg"), "2025-08-07_143052.jpg")]


def test_plan_datetime_same_second_gets_suffix(tmp_path):
    a = _photo(str(tmp_path / "a.jpg"), "2025-08-07T14:30:52")
    b = _photo(str(tmp_path / "b.jpg"), "2025-08-07T14:30:52")
    c = _photo(str(tmp_path / "c.jpg"), "2025-08-07T14:30:52")
    plan = plan_renames([a, b, c], "datetime")
    assert plan == [
        (str(tmp_path / "a.jpg"), "2025-08-07_143052.jpg"),
        (str(tmp_path / "b.jpg"), "2025-08-07_143052-2.jpg"),
        (str(tmp_path / "c.jpg"), "2025-08-07_143052-3.jpg"),
    ]


def test_plan_preserves_extension_exactly(tmp_path):
    a = _photo(str(tmp_path / "a.JPG"), "2025-08-07T08:00:00")
    b = _photo(str(tmp_path / "b.jpeg"), "2025-08-07T09:00:00")
    plan = plan_renames([a, b], "number")
    assert plan == [
        (str(tmp_path / "a.JPG"), "001.JPG"),
        (str(tmp_path / "b.jpeg"), "002.jpeg"),
    ]


def test_plan_skips_entries_already_named(tmp_path):
    # 001.jpg already named correctly -> skipped; 002 differs -> kept.
    a = _photo(str(tmp_path / "001.jpg"), "2025-08-07T08:00:00")
    b = _photo(str(tmp_path / "other.jpg"), "2025-08-07T09:00:00")
    plan = plan_renames([a, b], "number")
    assert plan == [(str(tmp_path / "other.jpg"), "002.jpg")]


def test_plan_custom_uses_safe_word(tmp_path):
    a = _photo(str(tmp_path / "a.jpg"), "2025-08-07T08:00:00")
    b = _photo(str(tmp_path / "b.jpg"), "2025-08-07T09:00:00")
    plan = plan_renames([a, b], "custom", word="Trip / 2025")
    safe = organize._safe_name("Trip / 2025")
    assert plan == [
        (str(tmp_path / "a.jpg"), f"{safe}_001.jpg"),
        (str(tmp_path / "b.jpg"), f"{safe}_002.jpg"),
    ]


def test_plan_custom_empty_word_raises(tmp_path):
    a = _photo(str(tmp_path / "a.jpg"), "2025-08-07T08:00:00")
    with pytest.raises(ValueError):
        plan_renames([a], "custom", word=None)
    with pytest.raises(ValueError):
        plan_renames([a], "custom", word="")
    # A word that sanitizes to nothing (only disallowed chars) also raises.
    with pytest.raises(ValueError):
        plan_renames([a], "custom", word="///")


def test_plan_unknown_fmt_raises(tmp_path):
    a = _photo(str(tmp_path / "a.jpg"), "2025-08-07T08:00:00")
    with pytest.raises(ValueError):
        plan_renames([a], "bogus")


# ---------------------------------------------------------------------------
# safe_word -- emoji-safe custom rename sanitizer
# ---------------------------------------------------------------------------

def test_safe_word_passes_emoji_cjk_accents():
    assert safe_word("🌊") == "🌊"
    assert safe_word("海") == "海"
    assert safe_word("café") == "café"
    assert safe_word("Tōkyō 旅行 🗼") == "Tōkyō 旅行 🗼"


def test_safe_word_strips_slash_colon_control_and_leading_dots():
    # POSIX/Finder-illegal chars removed.
    assert safe_word("a/b:c") == "abc"
    # Control chars (newline, tab, null) removed.
    assert safe_word("a\nb\tc\x00") == "abc"
    # Leading dots stripped (no hidden files); surrounding whitespace stripped.
    assert safe_word("  ..hidden  ") == "hidden"
    # A leading dot then an emoji.
    assert safe_word(".🌊") == "🌊"


def test_safe_word_empty_or_illegal_only_raises():
    with pytest.raises(ValueError):
        safe_word("")
    with pytest.raises(ValueError):
        safe_word("   ")
    with pytest.raises(ValueError):
        safe_word("///")
    with pytest.raises(ValueError):
        safe_word("...")


def test_plan_custom_emoji_word(tmp_path):
    a = _photo(str(tmp_path / "a.jpg"), "2025-08-07T08:00:00")
    plan = plan_renames([a], "custom", word="🌊")
    assert plan == [(str(tmp_path / "a.jpg"), "🌊_001.jpg")]


# ---------------------------------------------------------------------------
# format_label -- extension -> human folder label
# ---------------------------------------------------------------------------

def test_format_label_mapping(tmp_path):
    assert format_label("a.jpg") == "JPEG"
    assert format_label("a.jpeg") == "JPEG"
    assert format_label("a.heic") == "HEIC"
    assert format_label("a.heif") == "HEIC"
    assert format_label("a.cr3") == "RAW"
    assert format_label("a.nef") == "RAW"
    assert format_label("a.png") == "PNG"
    assert format_label("a.webp") == "WEBP"
    assert format_label("a.gif") == "GIF"
    assert format_label("a.bmp") == "BMP"
    assert format_label("a.tif") == "TIFF"
    assert format_label("a.tiff") == "TIFF"
    assert format_label("a.svg") == "SVG"


def test_format_label_case_insensitive(tmp_path):
    assert format_label("a.JPG") == "JPEG"
    assert format_label("a.JPEG") == "JPEG"
    assert format_label("a.Png") == "PNG"
    assert format_label("a.HEIC") == "HEIC"


def test_format_label_unknown_ext_uppercased():
    assert format_label("a.xyz") == "XYZ"
    assert format_label("a.psd") == "PSD"


def test_format_label_no_ext_is_other():
    assert format_label("README") == "OTHER"
    assert format_label("/some/dir/noext") == "OTHER"


# ---------------------------------------------------------------------------
# rename_files -- filesystem two-phase + undo
# ---------------------------------------------------------------------------

def test_rename_files_happy_path_and_undo_round_trip(tmp_path):
    a = tmp_path / "z.jpg"; a.write_text("A")
    b = tmp_path / "a.jpg"; b.write_text("B")
    renames = [(str(b), "001.jpg"), (str(a), "002.jpg")]
    n = organize.rename_files(tmp_path, renames)
    assert n == 2
    assert (tmp_path / "001.jpg").read_text() == "B"
    assert (tmp_path / "002.jpg").read_text() == "A"
    assert not (tmp_path / "z.jpg").exists() and not (tmp_path / "a.jpg").exists()
    organize.undo_last(tmp_path)
    assert (tmp_path / "z.jpg").read_text() == "A"
    assert (tmp_path / "a.jpg").read_text() == "B"


def test_rename_files_case_only_undo_round_trip(tmp_path):
    # A case-only rename (a.jpg -> A.jpg) records {from: a.jpg, to: A.jpg}. On a
    # case-insensitive filesystem these are the SAME file, so undo must recognize
    # the file's own 'to' slot across case and restore the exact original name
    # rather than mistaking it for a foreign occupant.
    a = tmp_path / "a.jpg"; a.write_text("A")
    organize.rename_files(tmp_path, [(str(a), "A.jpg")])
    assert (tmp_path / "A.jpg").read_text() == "A"
    organize.undo_last(tmp_path)
    restored = next(p for p in tmp_path.iterdir() if p.suffix == ".jpg")
    assert restored.name == "a.jpg"  # exact original basename
    assert restored.read_text() == "A"


def test_rename_files_undo_refuses_foreign_clobber(tmp_path):
    # The casefold fix to undo_last must not weaken foreign-clobber protection:
    # after a.jpg -> B.jpg, a genuinely different file dropped at the original
    # 'a.jpg' path must still block undo (no silent clobber).
    a = tmp_path / "a.jpg"; a.write_text("A")
    organize.rename_files(tmp_path, [(str(a), "B.jpg")])
    foreign = tmp_path / "a.jpg"; foreign.write_text("FOREIGN")
    with pytest.raises(FileExistsError):
        organize.undo_last(tmp_path)
    # Nothing moved; both files intact, manifest preserved for a later retry.
    assert foreign.read_text() == "FOREIGN"
    assert (tmp_path / "B.jpg").read_text() == "A"


def test_rename_files_case_swap_undo_round_trip(tmp_path):
    # Case-swap: a.jpg -> B.jpg and b.jpg -> A.jpg. Undo must restore the exact
    # original basenames and contents.
    a = tmp_path / "a.jpg"; a.write_text("A")
    b = tmp_path / "b.jpg"; b.write_text("B")
    organize.rename_files(tmp_path, [(str(a), "B.jpg"), (str(b), "A.jpg")])
    assert (tmp_path / "A.jpg").read_text() == "B"
    assert (tmp_path / "B.jpg").read_text() == "A"
    organize.undo_last(tmp_path)
    by_name = {p.name: p.read_text() for p in tmp_path.iterdir() if p.suffix == ".jpg"}
    assert by_name == {"a.jpg": "A", "b.jpg": "B"}


def test_rename_files_keeps_subfolder_files_in_place(tmp_path):
    sub = tmp_path / "sub"; sub.mkdir()
    x = sub / "x.jpg"; x.write_text("X")
    organize.rename_files(tmp_path, [(str(x), "001.jpg")])
    assert (sub / "001.jpg").read_text() == "X"
    assert not (tmp_path / "001.jpg").exists()  # stayed in its own dir


def test_rename_refuses_foreign_clobber(tmp_path):
    a = tmp_path / "a.jpg"; a.write_text("A")
    foreign = tmp_path / "001.jpg"; foreign.write_text("FOREIGN")
    with pytest.raises(FileExistsError):
        organize.rename_files(tmp_path, [(str(a), "001.jpg")])
    # Nothing moved, no manifest.
    assert a.read_text() == "A"
    assert foreign.read_text() == "FOREIGN"
    assert not organize.manifest_path(tmp_path).exists()


def test_rename_allows_chained_swap_via_two_phase(tmp_path):
    # a.jpg -> b.jpg while b.jpg -> c.jpg. b.jpg exists on disk but is itself a
    # src that vacates in phase 1, so the rename must be allowed.
    a = tmp_path / "a.jpg"; a.write_text("A")
    b = tmp_path / "b.jpg"; b.write_text("B")
    n = organize.rename_files(tmp_path, [(str(a), "b.jpg"), (str(b), "c.jpg")])
    assert n == 2
    assert (tmp_path / "b.jpg").read_text() == "A"
    assert (tmp_path / "c.jpg").read_text() == "B"
    assert not (tmp_path / "a.jpg").exists()


def test_rename_case_insensitive_dest_collision_raises_before_move(tmp_path):
    # Two dests differing only by case map to the same file on a
    # case-insensitive FS -> reject before any move, both files intact.
    a = tmp_path / "a.jpg"; a.write_text("A")
    b = tmp_path / "b.jpg"; b.write_text("B")
    with pytest.raises(FileExistsError):
        organize.rename_files(tmp_path, [(str(a), "IMG.jpg"), (str(b), "img.jpg")])
    assert a.read_text() == "A"
    assert b.read_text() == "B"
    assert not organize.manifest_path(tmp_path).exists()


def test_rename_missing_src_raises_before_move(tmp_path):
    a = tmp_path / "a.jpg"; a.write_text("A")
    missing = tmp_path / "missing.jpg"
    with pytest.raises(FileNotFoundError):
        organize.rename_files(tmp_path, [(str(a), "001.jpg"), (str(missing), "002.jpg")])
    # a.jpg untouched, no manifest.
    assert a.read_text() == "A"
    assert not (tmp_path / "001.jpg").exists()
    assert not organize.manifest_path(tmp_path).exists()
