from __future__ import annotations

from phota.models import Photo, Plan


def summarize_photos(photos: list[Photo]) -> dict:
    dates = sorted((p.captured_at[:10] for p in photos if p.captured_at))
    cameras = sorted({p.camera for p in photos if p.camera})
    series = len({p.series_id for p in photos if p.series_id is not None})
    return {
        "count": len(photos),
        "series": series,
        "cameras": cameras,
        "date_range": (dates[0], dates[-1]) if dates else (None, None),
    }


def plan_summary(plan: Plan) -> str:
    return f"Plan '{plan.name}': {len(plan.ops)} operation(s)"


def render_status(photos: list[Photo]) -> None:
    from rich.console import Console
    from rich.table import Table

    s = summarize_photos(photos)
    table = Table(title="phota status")
    table.add_column("metric")
    table.add_column("value")
    table.add_row("photos", str(s["count"]))
    table.add_row("series", str(s["series"]))
    table.add_row("cameras", ", ".join(s["cameras"]) or "-")
    lo, hi = s["date_range"]
    table.add_row("date range", f"{lo} .. {hi}" if lo else "-")
    Console().print(table)


def render_plan(plan: Plan) -> None:
    from rich.console import Console
    from rich.table import Table

    table = Table(title=plan_summary(plan))
    table.add_column("action")
    table.add_column("from")
    table.add_column("to")
    for op in plan.ops:
        table.add_row(op.action, op.src, op.dst)
    Console().print(table)
