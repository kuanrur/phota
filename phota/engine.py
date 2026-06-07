from __future__ import annotations

from datetime import datetime, timezone

from phota.index import Index
from phota.metadata import extract_metadata
from phota.quality import score_photo
from phota.grouping import assign_series, find_raw_jpeg_pairs
from phota.scan import scan_dir


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None).isoformat()


def build_index(directory) -> dict:
    """Scan a directory and update the index incrementally.

    Returns stats: {scanned, analyzed, skipped}.
    """
    idx = Index()
    idx.init_schema()
    known = idx.known_mtimes()

    found = scan_dir(directory)
    analyzed = 0
    skipped = 0
    for photo in found:
        if known.get(photo.id) == photo.mtime:
            skipped += 1
            continue
        meta = extract_metadata(photo.path, fallback_mtime=photo.mtime)
        for key, value in meta.items():
            setattr(photo, key, value)
        scores = score_photo(photo.path)
        photo.sharpness = scores["sharpness"]
        photo.exposure_score = scores["exposure_score"]
        photo.phash = scores["phash"]
        if scores["sharpness"] is None:
            photo.error = "unreadable"
        photo.analyzed_at = _now_iso()
        idx.upsert_photo(photo)
        analyzed += 1

    # Re-group over the full set so series ids stay consistent.
    all_photos = idx.all_photos()
    assign_series(all_photos)
    for p in all_photos:
        idx.set_series(p.id, p.series_id)
    idx.conn.execute("DELETE FROM pairs")
    for raw_id, jpeg_id in find_raw_jpeg_pairs(all_photos):
        idx.add_pair(raw_id, jpeg_id)

    return {"scanned": len(found), "analyzed": analyzed, "skipped": skipped}
