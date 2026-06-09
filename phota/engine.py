from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from phota.index import Index
from phota.metadata import extract_metadata
from phota.quality import score_photo
from phota.grouping import assign_series, find_raw_jpeg_pairs
from phota.scan import scan_dir

# Image decoding dominates indexing time and releases the GIL (PIL/cv2), so
# analysis parallelizes well across cores. Measured ~5.7x on an 11-core M-series.
_ANALYZE_WORKERS = min(8, os.cpu_count() or 4)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None).isoformat()


def _analyze(photo):
    """CPU/IO-heavy per-photo work, safe to run off the main thread.

    Mutates and returns the photo; no database access here (SQLite writes
    stay on the calling thread).
    """
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
    return photo


def build_index(directory, db_path=None, progress=None) -> dict:
    """Scan a directory and update the index incrementally.

    Returns stats: {scanned, analyzed, skipped}.

    `progress`, if given, is called as progress(done, total) once after the set
    of new/changed photos is computed and again after each upsert. The upsert
    loop runs on the single calling thread, so no locking is needed.
    """
    idx = Index(db_path)
    idx.init_schema()
    known = idx.known_mtimes()

    found = scan_dir(directory)
    skipped = 0
    to_analyze = []
    for photo in found:
        if known.get(photo.id) == photo.mtime:
            skipped += 1
        else:
            to_analyze.append(photo)

    analyzed = 0
    if progress:
        progress(0, len(to_analyze))
    if to_analyze:
        with ThreadPoolExecutor(max_workers=_ANALYZE_WORKERS) as ex:
            for photo in ex.map(_analyze, to_analyze):
                idx.upsert_photo(photo)
                analyzed += 1
                if progress:
                    progress(analyzed, len(to_analyze))

    pruned = idx.prune({p.id for p in found})

    # Re-group over the full set so series ids stay consistent.
    all_photos = idx.all_photos()
    assign_series(all_photos)
    for p in all_photos:
        idx.set_series(p.id, p.series_id)
    idx.clear_pairs()
    for raw_id, jpeg_id in find_raw_jpeg_pairs(all_photos):
        idx.add_pair(raw_id, jpeg_id)

    return {"scanned": len(found), "analyzed": analyzed, "skipped": skipped, "pruned": pruned}
