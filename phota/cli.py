from __future__ import annotations

import typer

from phota.engine import build_index
from phota.index import Index
from phota.models import Plan
from phota.plan import apply_plan, load_plan, save_plan
from phota import output, workflows

app = typer.Typer(help="phota — customizable photo sorting")


def _load_photos() -> list:
    idx = Index()
    idx.init_schema()
    return idx.all_photos()


@app.command()
def scan(directory: str = typer.Argument(...)):
    """Build or update the index for a photo directory."""
    stats = build_index(directory)
    typer.echo(
        f"scanned {stats['scanned']}, analyzed {stats['analyzed']}, "
        f"skipped {stats['skipped']}"
    )


@app.command()
def status():
    """Show a summary of the indexed photos."""
    output.render_status(_load_photos())


@app.command()
def series():
    """List detected series with the suggested keeper per series."""
    photos = _load_photos()
    plan = workflows.cull(photos, out_dir="phota-out/keepers")
    output.render_plan(plan)


@app.command()
def cull(
    ai: bool = typer.Option(False, help="use AI to break ties on aesthetics"),
    plan: str = typer.Option("phota-out/cull.json", "--plan"),
    out: str = typer.Option("phota-out/keepers", "--out"),
):
    """Pick the best frame per burst into a plan."""
    photos = _load_photos()
    if ai:
        from phota.ai import rank_with_ai

        photos = rank_with_ai(photos)
    p = workflows.cull(photos, out_dir=out)
    save_plan(p, plan)
    output.render_plan(p)
    typer.echo(f"plan written to {plan}")


@app.command()
def organize(
    by: str = typer.Option("date", help="date|event|camera"),
    plan: str = typer.Option("phota-out/organize.json", "--plan"),
    out: str = typer.Option("phota-out/organized", "--out"),
):
    """Build a folder-tree plan."""
    p = workflows.organize(_load_photos(), by=by, out_dir=out)
    save_plan(p, plan)
    output.render_plan(p)
    typer.echo(f"plan written to {plan}")


@app.command()
def curate(
    name: str = typer.Argument(...),
    camera: str = typer.Option(None),
    after: str = typer.Option(None),
    before: str = typer.Option(None),
    plan: str = typer.Option("phota-out/curate.json", "--plan"),
    out: str = typer.Option("phota-out/curated", "--out"),
):
    """Assemble a named publishing set."""
    p = workflows.curate(
        _load_photos(), name=name, out_dir=out,
        camera=camera, after=after, before=before,
    )
    save_plan(p, plan)
    output.render_plan(p)
    typer.echo(f"plan written to {plan}")


@app.command(name="edit-list")
def edit_list(
    plan: str = typer.Option("phota-out/edit-list.json", "--plan"),
    out: str = typer.Option("phota-out/to-edit", "--out"),
):
    """Flag raws worth editing as symlinks for Lightroom."""
    p = workflows.edit_list(_load_photos(), out_dir=out)
    save_plan(p, plan)
    output.render_plan(p)
    typer.echo(f"plan written to {plan}")


@app.command()
def find(
    query: str = typer.Argument(None, help="semantic query (needs --ai tags)"),
    camera: str = typer.Option(None),
    lens: str = typer.Option(None),
    after: str = typer.Option(None),
    before: str = typer.Option(None),
):
    """Find photos by metadata filters or a semantic query."""
    photos = _load_photos()
    ids = None
    if query:
        from phota.ai import semantic_match

        ids = semantic_match(photos, query)
    results = workflows.find(
        photos, camera=camera, lens=lens, after=after, before=before, ids=ids
    )
    for p in results:
        typer.echo(f"{p.captured_at}  {p.camera or '-':10}  {p.path}")
    typer.echo(f"{len(results)} match(es)")


@app.command()
def apply(
    plan_path: str = typer.Argument(...),
    move: bool = typer.Option(False, help="move originals instead of copying"),
    yes: bool = typer.Option(False, "--yes", help="skip confirmation"),
):
    """Execute a saved plan (the only mutating command)."""
    plan = load_plan(plan_path)
    mode = "move" if move else "copy"
    output.render_plan(plan)
    if not yes:
        typer.confirm(f"Apply {len(plan.ops)} op(s) in {mode} mode?", abort=True)
    apply_plan(plan, mode=mode)
    typer.echo("done")
