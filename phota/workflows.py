from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from phota.grouping import assign_events
from phota.models import Photo, Plan, PlanOp


def _keeper_per_series(photos: list[Photo]) -> list[Photo]:
    by_series: dict[int, list[Photo]] = defaultdict(list)
    for p in photos:
        by_series[p.series_id].append(p)
    keepers = []
    for series in by_series.values():
        best = max(
            series,
            key=lambda p: (p.sharpness or 0.0, getattr(p, "_aesthetic", 0.0)),
        )
        keepers.append(best)
    return keepers


def cull(photos: list[Photo], out_dir: str) -> Plan:
    keepers = _keeper_per_series(photos)
    ops = [
        PlanOp("copy", p.path, str(Path(out_dir) / p.filename), p.id)
        for p in keepers
    ]
    return Plan(name="cull", ops=ops)


def organize(photos: list[Photo], by: str, out_dir: str) -> Plan:
    ops = []
    events = assign_events(photos) if by == "event" else {}
    for p in photos:
        if by == "date":
            bucket = (p.captured_at or "unknown")[:10]
        elif by == "camera":
            bucket = p.camera or "unknown"
        elif by == "event":
            bucket = f"event-{events.get(p.id, 0):03d}"
        else:
            raise ValueError(f"unknown grouping {by}")
        ops.append(PlanOp("copy", p.path, str(Path(out_dir) / bucket / p.filename), p.id))
    return Plan(name=f"organize-{by}", ops=ops)


def curate(photos: list[Photo], name: str, out_dir: str, **filters) -> Plan:
    selected = find(photos, **filters)
    ops = [
        PlanOp("copy", p.path, str(Path(out_dir) / name / p.filename), p.id)
        for p in selected
    ]
    return Plan(name=f"curate-{name}", ops=ops)


def edit_list(photos: list[Photo], out_dir: str) -> Plan:
    keepers = _keeper_per_series([p for p in photos if p.kind == "raw"])
    ops = [
        PlanOp("symlink", p.path, str(Path(out_dir) / p.filename), p.id)
        for p in keepers
    ]
    return Plan(name="edit-list", ops=ops)


def find(
    photos: list[Photo],
    camera: str | None = None,
    lens: str | None = None,
    after: str | None = None,
    before: str | None = None,
    ids: set[str] | None = None,
) -> list[Photo]:
    out = []
    for p in photos:
        if camera and p.camera != camera:
            continue
        if lens and p.lens != lens:
            continue
        if after and (p.captured_at or "") < after:
            continue
        if before and (p.captured_at or "") > before:
            continue
        if ids is not None and p.id not in ids:
            continue
        out.append(p)
    return out
