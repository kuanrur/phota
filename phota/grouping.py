from __future__ import annotations

from datetime import datetime
from pathlib import Path

from phota.config import SERIES_GAP_SECONDS, EVENT_GAP_SECONDS
from phota.models import Photo


def _ts(photo: Photo) -> datetime:
    return datetime.fromisoformat(photo.captured_at)


def _sorted(photos: list[Photo]) -> list[Photo]:
    return sorted([p for p in photos if p.captured_at], key=_ts)


def assign_series(photos: list[Photo]) -> None:
    """Mutate photos in place, setting series_id by time-proximity clusters."""
    ordered = _sorted(photos)
    series_id = 0
    prev = None
    for p in ordered:
        if prev is not None and (_ts(p) - _ts(prev)).total_seconds() > SERIES_GAP_SECONDS:
            series_id += 1
        p.series_id = series_id
        prev = p


def assign_events(photos: list[Photo]) -> dict[str, int]:
    """Return {photo_id: event_id}; events split on large time gaps."""
    ordered = _sorted(photos)
    out: dict[str, int] = {}
    event_id = 0
    prev = None
    for p in ordered:
        if prev is not None and (_ts(p) - _ts(prev)).total_seconds() > EVENT_GAP_SECONDS:
            event_id += 1
        out[p.id] = event_id
        prev = p
    return out


def find_raw_jpeg_pairs(photos: list[Photo]) -> list[tuple[str, str]]:
    """Pair a raw and a jpeg that share a basename (e.g. IMG_1936)."""
    by_stem: dict[str, dict[str, str]] = {}
    for p in photos:
        stem = Path(p.filename).stem.lower()
        by_stem.setdefault(stem, {})[p.kind] = p.id
    pairs = []
    for stem, kinds in by_stem.items():
        if "raw" in kinds and "jpeg" in kinds:
            pairs.append((kinds["raw"], kinds["jpeg"]))
    return pairs
