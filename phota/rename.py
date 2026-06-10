"""Pure name planning for batch renames -- no filesystem access.

``plan_renames`` turns an iterable of photos into a list of
``(abs_src_path, new_basename)`` pairs. The caller (``organize.rename_files``)
performs the actual two-phase, reversible moves.
"""
import re
import unicodedata
from pathlib import Path


def safe_word(word) -> str:
    """Sanitize a custom rename word permissively, preserving unicode.

    NFC-normalizes, drops unicode control chars (category starting with 'C'),
    removes '/' and ':' (POSIX/Finder-illegal in a basename), strips surrounding
    whitespace and leading dots (so no hidden files). Emoji, CJK and accented
    characters all pass through. Raises ValueError if nothing survives.
    """
    word = unicodedata.normalize("NFC", word or "")
    word = "".join(
        ch
        for ch in word
        if not unicodedata.category(ch).startswith("C") and ch not in "/:"
    )
    # Strip mixed runs of dots and whitespace from the front ('. . tokyo' ->
    # 'tokyo'), not just one contiguous dot run -- no hidden-file basenames.
    word = re.sub(r"^[.\s]+", "", word).strip()
    if not word:
        raise ValueError("custom rename requires a non-empty word")
    return word


def plan_renames(photos, fmt, word=None):
    """Plan new basenames for ``photos`` under ``fmt``.

    photos: iterable with ``.path`` / ``.filename`` / ``.captured_at``.
    Sorted by ``(captured_at or '', filename)``. Returns
    ``[(abs_src_path, new_basename)]`` in that order, SKIPPING entries whose
    new basename equals the current one. The original file extension is
    preserved exactly (the src suffix as-is). Raises ValueError on an unknown
    ``fmt`` or an empty ``custom`` word.
    """
    items = sorted(photos, key=lambda p: (p.captured_at or "", p.filename))
    total = len(items)

    if fmt == "number":
        pad = max(3, len(str(total)))
        new_names = [str(i).zfill(pad) for i in range(1, total + 1)]
    elif fmt == "custom":
        # safe_word raises ValueError when the word is missing or sanitizes to
        # nothing; emoji/CJK/accents pass through unchanged.
        safe = safe_word(word)
        pad = max(3, len(str(total)))
        new_names = [f"{safe}_{str(i).zfill(pad)}" for i in range(1, total + 1)]
    elif fmt == "date_number":
        # Counter restarts per day; padding is per-day max(2, digits of count).
        by_day = {}
        for p in items:
            by_day.setdefault((p.captured_at or "")[:10], []).append(p)
        pad_for = {
            day: max(2, len(str(len(members)))) for day, members in by_day.items()
        }
        counter = {}
        new_names = []
        for p in items:
            day = (p.captured_at or "")[:10]
            counter[day] = counter.get(day, 0) + 1
            new_names.append(f"{day}_{str(counter[day]).zfill(pad_for[day])}")
    elif fmt == "datetime":
        # 2025-08-07T14:30:52 -> 2025-08-07_143052. Collisions within the same
        # second get -2, -3 ... appended (the first keeps the plain stem).
        seen = {}
        new_names = []
        for p in items:
            ca = p.captured_at or ""
            stem = ca[:19].replace("T", "_").replace(":", "")
            seen[stem] = seen.get(stem, 0) + 1
            if seen[stem] > 1:
                stem = f"{stem}-{seen[stem]}"
            new_names.append(stem)
    else:
        raise ValueError(f"unknown rename format: {fmt}")

    plan = []
    for p, stem in zip(items, new_names):
        src = Path(p.path)
        new_basename = stem + src.suffix
        if new_basename == src.name:
            continue
        plan.append((str(src), new_basename))
    return plan
