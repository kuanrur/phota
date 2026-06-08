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
    ops = [
        PlanOp("copy", p.path, str(Path(out_dir) / label / p.filename), p.id)
        for p in photos
    ]
    return Plan(name=f"export-{label}", ops=ops)
