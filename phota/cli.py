from __future__ import annotations

import os
from pathlib import Path

import typer

from phota.engine import build_index
from phota.index import Index
from phota.plan import apply_plan, load_plan, save_plan
from phota.server import create_app
from phota.config import library_db_path
from phota import output, workflows

app = typer.Typer(help="phota — customizable photo sorting")


def open_app_window(url: str) -> None:
    """Open the window as a standalone app window, not a tab in the user's
    existing browser. Uses a Chromium browser's --app mode with a dedicated
    profile so it spawns its own chromeless window; falls back to the default
    browser if no Chromium browser is found."""
    import subprocess
    import sys

    if sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
        profile = str(Path.home() / ".phota" / "browser")
        for binpath in candidates:
            if os.path.exists(binpath):
                subprocess.Popen(
                    [
                        binpath,
                        f"--app={url}",
                        f"--user-data-dir={profile}",
                        "--window-size=980,700",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
    import webbrowser

    webbrowser.open(url)


def launch(folder=None, open_browser=True, serve=True):
    # When a folder is given (`phota <dir>`), pre-index it and open straight to it.
    # When none is given (bare `phota`), open with no active folder so the
    # controller shows the Finder-folder picker and the user chooses.
    if folder is not None:
        folder = os.path.abspath(folder)
        # Per-folder library: point PHOTA_DB at the folder's own db so different
        # folders never share state. Respect a genuinely external PHOTA_DB
        # (tests, power users) that the launcher did not set itself.
        user_override = (
            "PHOTA_DB" in os.environ
            and os.environ.get("_PHOTA_DB_OWNER") != os.environ["PHOTA_DB"]
        )
        if not user_override:
            p = str(library_db_path(folder))
            os.environ["PHOTA_DB"] = p
            os.environ["_PHOTA_DB_OWNER"] = p
        from phota.engine import build_index

        build_index(folder)
    fastapi_app = create_app(folder)
    if serve:
        import socket
        import threading

        import uvicorn

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        url = f"http://127.0.0.1:{port}"
        if open_browser:
            threading.Timer(0.6, lambda: open_app_window(url)).start()
        uvicorn.run(fastapi_app, host="127.0.0.1", port=port)
    return fastapi_app, folder


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        launch(None)


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
        if ids is None:
            typer.echo("semantic search unavailable: set ANTHROPIC_API_KEY")
            raise typer.Exit()
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
    manifest = apply_plan(plan, mode=mode)
    if mode == "move":
        import json
        from pathlib import Path

        manifest_path = plan_path + ".manifest.json"
        Path(manifest_path).write_text(json.dumps(manifest, indent=2))
        typer.echo(f"manifest written to {manifest_path}")
    typer.echo("done")


@app.command()
def undo(manifest_path: str = typer.Argument(...)):
    """Reverse a move applied earlier, using its manifest."""
    import json
    from pathlib import Path
    from phota.plan import reverse_manifest
    manifest = json.loads(Path(manifest_path).read_text())
    reverse_manifest(manifest)
    typer.echo("reversed")


@app.command()
def open(directory: str = typer.Argument(None)):
    """Open the phota control window on a folder (default: current dir)."""
    launch(directory)


# Command names registered on the Typer app. A leading token matching one of
# these dispatches to the CLI; a leading directory opens the window directly.
_COMMANDS = {
    "scan", "status", "series", "cull", "organize", "curate",
    "edit-list", "find", "apply", "undo", "open",
}


def main() -> None:
    """Console entry point.

    `phota`              -> open the window on the current folder
    `phota <dir>`        -> open the window on <dir>
    `phota <command> ...`-> run the CLI subcommand
    """
    import sys

    argv = sys.argv[1:]
    if not argv:
        launch(None)
        return
    first = argv[0]
    if first not in _COMMANDS and not first.startswith("-"):
        candidate = os.path.abspath(os.path.expanduser(first))
        if os.path.isdir(candidate):
            launch(candidate)
            return
    app()
