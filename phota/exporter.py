from __future__ import annotations

from pathlib import Path

from phota import store
from phota.models import Plan, PlanOp


def build_export_plan(idx, scope, out_dir):
    if scope == "keepers":
        label = "keepers"
        photos = [p for p in idx.all_photos() if store.get_keep(idx, p.id) is True]
    elif scope == "all":
        label = "all"
        photos = idx.all_photos()
    elif scope.startswith("album:"):
        label = scope.split(":", 1)[1]
        ids = set(store.photos_in_album(idx, label))
        photos = [p for p in idx.all_photos() if p.id in ids]
    else:
        raise ValueError(f"unknown scope {scope}")
    dest_dir = Path(out_dir) / label
    # Count basenames so we only disambiguate the ones that actually collide.
    counts: dict[str, int] = {}
    for p in photos:
        counts[p.filename] = counts.get(p.filename, 0) + 1
    ops = []
    for p in photos:
        if counts[p.filename] > 1:
            stem = Path(p.filename).stem
            ext = Path(p.filename).suffix
            name = f"{stem}__{p.id[:8]}{ext}"
        else:
            name = p.filename
        ops.append(PlanOp("copy", p.path, str(dest_dir / name), p.id))
    return Plan(name=f"export-{label}", ops=ops)
