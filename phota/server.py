from __future__ import annotations

import os
import threading
from collections import defaultdict
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from phota import ai
from phota import config as _config
from phota import store, thumbs
from phota.config import library_db_path
from phota.engine import build_index
from phota.index import Index
from phota.output import summarize_photos
from phota.providers import get_provider


class AiSettings(BaseModel):
    provider: str
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class FolderBody(BaseModel):
    path: str
    wait: bool = False


class OrderBody(BaseModel):
    ordered_ids: list[str]


class SortBody(BaseModel):
    folder_name: str
    ids: list[str]


class OrganizeBody(BaseModel):
    action: str


class TidyBody(BaseModel):
    action: str


class RenameBody(BaseModel):
    fmt: str
    word: str | None = None
    dry_run: bool = False


def reveal_in_finder(path):
    import subprocess

    subprocess.run(["open", "-R", path])


def open_in_default_app(path):
    import subprocess

    subprocess.run(["open", path])


def _finder_url_to_path(url: str):
    """Convert a Finder file:// URL to an absolute POSIX path (or None)."""
    from urllib.parse import unquote, urlparse

    parsed = urlparse(url.strip())
    if parsed.scheme != "file" or not parsed.path:
        return None
    return unquote(parsed.path).rstrip("/") or "/"


# Detect folders from Finder via three sources, most-specific first. We read
# the `URL of` each target rather than coercing to `alias`: inside a
# `repeat with x in (every ...)` the loop var is a list specifier and
# `x as alias` raises "Can't make ... into type alias", which silently broke
# the old detector.
_SCRIPT_SELECTION = (
    'tell application "Finder"\n'
    "set out to {}\n"
    "repeat with anItem in (get selection)\n"
    "try\n"
    "set end of out to (URL of (anItem as alias))\n"
    "end try\n"
    "end repeat\n"
    "set AppleScript's text item delimiters to linefeed\n"
    "return out as text\n"
    "end tell"
)
_SCRIPT_FRONT = 'tell application "Finder" to get URL of (insertion location as alias)'
_SCRIPT_WINDOWS = (
    'tell application "Finder"\n'
    "set theURLs to URL of (target of every Finder window)\n"
    "set AppleScript's text item delimiters to linefeed\n"
    "return theURLs as text\n"
    "end tell"
)


def _run_osascript(script):
    """Return (stdout, error). error is 'permission' when Finder access is
    blocked, else None. Non-permission failures return ('', None)."""
    import subprocess

    try:
        res = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=5
        )
    except Exception:
        return "", None
    if res.returncode != 0:
        err = res.stderr or ""
        if "-1743" in err or "Not authorized" in err:
            return "", "permission"
        return "", None
    return res.stdout, None


def detect_finder_folders():
    """Return (paths, error) for folders the user has selected/open in Finder.

    Order: a highlighted folder selection, then the front window's folder, then
    every other open window. `error` is 'permission' when macOS Automation
    access to Finder is denied and nothing could be read.
    """
    paths: list[str] = []
    permission_blocked = False
    for script in (_SCRIPT_SELECTION, _SCRIPT_FRONT, _SCRIPT_WINDOWS):
        out, err = _run_osascript(script)
        if err == "permission":
            permission_blocked = True
        for line in (out or "").splitlines():
            p = _finder_url_to_path(line)
            if p and os.path.isdir(p) and p not in paths:
                paths.append(p)
    error = "permission" if (permission_blocked and not paths) else None
    return paths, error


def _applescript_quote(path: str) -> str:
    """Escape a POSIX path for embedding inside an AppleScript string literal."""
    return path.replace("\\", "\\\\").replace('"', '\\"')


def _finder_cleanup_script(folder: str) -> str:
    """AppleScript: find the Finder window whose target is `folder` (opening it
    if none exists), switch it to icon view, and clean up by name.

    We compute the target URL from `POSIX file ... as alias` so it matches the
    URL form Finder itself reports (symlinks resolved the same way, e.g.
    /tmp -> /private/tmp). Windows are iterated by index inside try blocks: a
    `repeat with w in (every Finder window)` loop var is a list specifier whose
    `target of w` coercion can fail, which historically broke detection. The
    script returns 'ok' / 'no-window' so Python can map the outcome.
    """
    p = _applescript_quote(folder)
    return (
        'tell application "Finder"\n'
        f'set targetURL to URL of (POSIX file "{p}" as alias)\n'
        "set theWin to missing value\n"
        "repeat with i from 1 to (count of Finder windows)\n"
        "try\n"
        "if (URL of (target of Finder window i)) is targetURL then\n"
        "set theWin to Finder window i\n"
        "exit repeat\n"
        "end if\n"
        "end try\n"
        "end repeat\n"
        "if theWin is missing value then\n"
        f'open (POSIX file "{p}" as alias)\n'
        "delay 0.5\n"
        "repeat with i from 1 to (count of Finder windows)\n"
        "try\n"
        "if (URL of (target of Finder window i)) is targetURL then\n"
        "set theWin to Finder window i\n"
        "exit repeat\n"
        "end if\n"
        "end try\n"
        "end repeat\n"
        "end if\n"
        'if theWin is missing value then return "no-window"\n'
        "set current view of theWin to icon view\n"
        "clean up theWin by name\n"
        'return "ok"\n'
        "end tell"
    )


def _finder_arrange_script(folder: str, on: bool) -> str:
    """AppleScript: set the folder's icon-view arrangement to 'arranged by name'
    (keep on) or 'not arranged' (keep off). Operates on `window of folder ...`,
    which resolves the folder's view options whether or not a window is open."""
    p = _applescript_quote(folder)
    value = "arranged by name" if on else "not arranged"
    return (
        'tell application "Finder"\n'
        f"set arrangement of icon view options of window of folder "
        f'(POSIX file "{p}" as alias) to {value}\n'
        'return "ok"\n'
        "end tell"
    )


def _finder_arrangement_read_script(folder: str) -> str:
    """AppleScript: return the folder's current icon-view arrangement as text
    (e.g. 'arranged by name', 'not arranged', 'snap to grid')."""
    p = _applescript_quote(folder)
    return (
        'tell application "Finder"\n'
        f"return (arrangement of icon view options of window of folder "
        f'(POSIX file "{p}" as alias)) as text\n'
        "end tell"
    )


def _photo_dict(idx, p) -> dict:
    return {
        "id": p.id,
        "filename": p.filename,
        "captured_at": p.captured_at,
        "camera": p.camera,
        "lens": p.lens,
        "series_id": p.series_id,
        "sharpness": p.sharpness,
        "keep": store.get_keep(idx, p.id),
        "albums": store.albums_for(idx, p.id),
        "thumb_url": f"/api/thumb/{p.id}",
    }


def create_app(folder: str | None = None) -> FastAPI:
    app = FastAPI()
    app.state.folder = folder
    app.state.db_path = os.environ.get("PHOTA_DB") or (
        str(library_db_path(folder)) if folder else None
    )
    app.state.index_job = {
        "running": False,
        "done": 0,
        "total": 0,
        "folder": None,
        "count": None,
        "error": None,
    }
    # Serializes every build_index call (and the open-folder check-then-set) so
    # two index passes never prune()/rewrite series_id over the same db at once.
    app.state.index_lock = threading.Lock()

    def _index() -> Index:
        idx = Index(app.state.db_path)
        idx.init_schema()
        return idx

    def _guard_indexing() -> None:
        if app.state.index_job["running"]:
            raise HTTPException(status_code=409, detail="indexing in progress")

    def _rebuild() -> None:
        """Re-index the active folder, serialized so it never overlaps the
        background indexer from open-folder."""
        with app.state.index_lock:
            build_index(app.state.folder, db_path=app.state.db_path)

    @app.get("/api/finder-folders")
    def finder_folders():
        paths, error = detect_finder_folders()
        return {
            "folders": [
                {"path": p, "name": os.path.basename(p.rstrip("/")) or p}
                for p in paths
            ],
            "error": error,
        }

    @app.post("/api/finder-tidy")
    def finder_tidy(body: TidyBody):
        folder = app.state.folder
        if not folder:
            raise HTTPException(status_code=400, detail="no active folder")
        if body.action == "cleanup":
            script = _finder_cleanup_script(folder)
        elif body.action in ("keep_on", "keep_off"):
            script = _finder_arrange_script(folder, on=body.action == "keep_on")
        else:
            raise HTTPException(status_code=400, detail="unknown action")
        out, err = _run_osascript(script)
        if err == "permission":
            return {"ok": False, "error": "permission"}
        result = (out or "").strip()
        if result == "ok":
            return {"ok": True}
        if result == "no-window":
            return {"ok": False, "error": "no-window"}
        # Any other non-ok output is a script-level failure; surface it.
        return {"ok": False, "error": result or "failed"}

    @app.get("/api/finder-tidy")
    def finder_tidy_status():
        folder = app.state.folder
        if not folder:
            raise HTTPException(status_code=400, detail="no active folder")
        out, err = _run_osascript(_finder_arrangement_read_script(folder))
        if err == "permission":
            return {"arranged": None, "error": "permission"}
        result = (out or "").strip().lower()
        if result in ("arranged by name", "snap to grid") or result.startswith(
            "arranged"
        ):
            return {"arranged": True}
        if result == "not arranged":
            return {"arranged": False}
        return {"arranged": None}

    @app.post("/api/open-folder")
    def open_folder(body: FolderBody):
        folder = os.path.abspath(os.path.expanduser(body.path))
        dbp = str(library_db_path(folder))
        # Atomically reject if a prior job is still running, else claim the slot.
        # Holding index_lock here makes the check-then-set safe against a
        # concurrent open-folder/mutation racing the same db.
        with app.state.index_lock:
            if app.state.index_job["running"]:
                raise HTTPException(status_code=409, detail="indexing in progress")
            app.state.folder = folder
            app.state.db_path = dbp
            job = {
                "running": True,
                "done": 0,
                "total": 0,
                "folder": folder,
                "count": None,
                "error": None,
            }
            app.state.index_job = job

        def _progress(done, total):
            job["done"] = done
            job["total"] = total

        def _run():
            try:
                with app.state.index_lock:
                    build_index(folder, db_path=dbp, progress=_progress)
                    job["count"] = len(Index(dbp).all_photos())
            except Exception as e:
                job["error"] = str(e)
            finally:
                job["running"] = False

        if body.wait:
            _run()
            if job["error"]:
                raise HTTPException(status_code=500, detail=job["error"])
            return {"folder": folder, "count": job["count"]}

        threading.Thread(target=_run, daemon=True).start()
        return {"folder": folder, "indexing": True}

    @app.get("/api/index-status")
    def index_status():
        return app.state.index_job

    @app.get("/api/library")
    def library():
        idx = _index()
        ph = idx.all_photos()
        s = summarize_photos(ph)
        return {
            "folder": app.state.folder,
            "count": s["count"],
            "cameras": s["cameras"],
            "date_range": s["date_range"],
            "series": s["series"],
        }

    @app.get("/api/photos")
    def photos(
        album: str | None = None,
        camera: str | None = None,
        after: str | None = None,
        before: str | None = None,
        bursts_only: bool = False,
        keep: str | None = None,
    ):
        idx = _index()
        ph = idx.all_photos()

        if album is not None:
            in_album = set(store.photos_in_album(idx, album))
            ph = [p for p in ph if p.id in in_album]

        if camera is not None:
            ph = [p for p in ph if p.camera == camera]

        if after is not None:
            ph = [p for p in ph if p.captured_at and p.captured_at >= after]

        if before is not None:
            bound = before + "T23:59:59" if len(before) == 10 else before
            ph = [p for p in ph if p.captured_at and p.captured_at <= bound]

        if bursts_only:
            counts: dict = defaultdict(int)
            for p in idx.all_photos():
                if p.series_id is not None:
                    counts[p.series_id] += 1
            ph = [p for p in ph if p.series_id is not None and counts[p.series_id] > 1]

        if keep is not None:
            def _state(p):
                k = store.get_keep(idx, p.id)
                if k is True:
                    return "keep"
                if k is False:
                    return "reject"
                return "undecided"

            ph = [p for p in ph if _state(p) == keep]

        return [_photo_dict(idx, p) for p in ph]

    @app.get("/api/series")
    def series():
        idx = _index()
        groups: dict = defaultdict(list)
        for p in idx.all_photos():
            if p.series_id is None:
                continue
            groups[p.series_id].append(p)
        out = []
        for sid, members in groups.items():
            keeper = max(members, key=lambda p: (p.sharpness or 0))
            out.append(
                {
                    "series_id": sid,
                    "photo_ids": [p.id for p in members],
                    "suggested_keeper_id": keeper.id,
                }
            )
        return out

    @app.get("/api/thumb/{photo_id}")
    def thumb(photo_id: str):
        idx = _index()
        p = idx.get_photo(photo_id)
        if not p:
            raise HTTPException(status_code=404)
        t = thumbs.get_or_build_thumb(p)
        if not t:
            raise HTTPException(status_code=404)
        return FileResponse(t, media_type="image/jpeg")

    @app.get("/api/full/{photo_id}")
    def full(photo_id: str):
        idx = _index()
        p = idx.get_photo(photo_id)
        if not p:
            raise HTTPException(status_code=404)
        t = thumbs.get_or_build_preview(p)
        if not t:
            raise HTTPException(status_code=404)
        return FileResponse(t, media_type="image/jpeg")

    @app.post("/api/photos/{photo_id}/keep")
    def set_keep(photo_id: str, keep: bool | None = Body(None, embed=True)):
        idx = _index()
        if idx.get_photo(photo_id) is None:
            raise HTTPException(status_code=404)
        store.set_keep(idx, photo_id, keep)
        return {"ok": True}

    @app.get("/api/albums")
    def albums():
        idx = _index()
        return store.list_albums(idx)

    @app.post("/api/albums")
    def create_album(name: str = Body(..., embed=True)):
        idx = _index()
        store.create_album(idx, name)
        return {"ok": True}

    @app.delete("/api/albums/{name}")
    def delete_album(name: str):
        idx = _index()
        store.delete_album(idx, name)
        return {"ok": True}

    @app.post("/api/albums/{name}/photos")
    def add_to_album(name: str, ids: list[str] = Body(..., embed=True)):
        idx = _index()
        store.add_to_album(idx, name, ids)
        return {"ok": True}

    @app.delete("/api/albums/{name}/photos")
    def remove_from_album(name: str, ids: list[str] = Body(..., embed=True)):
        idx = _index()
        store.remove_from_album(idx, name, ids)
        return {"ok": True}

    @app.post("/api/export")
    def export(
        scope: str = Body(..., embed=True),
        mode: str = Body("copy", embed=True),
        out_dir: str = Body(..., embed=True),
    ):
        import json

        from phota import exporter
        from phota.plan import apply_plan

        idx = _index()
        plan = exporter.build_export_plan(idx, scope, out_dir)
        # Pre-validate BEFORE executing any op so a move never runs partway
        # and leaves an irreversible, unrecorded mutation. Reject duplicate
        # or pre-existing destinations with a clean 409 and zero filesystem
        # mutation.
        seen: set[str] = set()
        for op in plan.ops:
            if op.dst in seen or Path(op.dst).exists():
                raise HTTPException(
                    status_code=409,
                    detail=f"destination conflict: {op.dst}",
                )
            seen.add(op.dst)
        try:
            manifest = apply_plan(plan, mode=mode)
        except (FileExistsError, ValueError) as e:
            raise HTTPException(status_code=409, detail=str(e))
        result = {"count": len(plan.ops)}
        if mode == "move":
            mpath = str(Path(out_dir) / "export.manifest.json")
            Path(mpath).parent.mkdir(parents=True, exist_ok=True)
            Path(mpath).write_text(json.dumps(manifest, indent=2))
            result["manifest_path"] = mpath
        return result

    @app.post("/api/reveal/{photo_id}")
    def reveal(photo_id: str):
        idx = _index()
        p = idx.get_photo(photo_id)
        if p is None:
            raise HTTPException(status_code=404)
        reveal_in_finder(p.path)
        return {"ok": True}

    @app.post("/api/open/{photo_id}")
    def open_photo(photo_id: str):
        idx = _index()
        p = idx.get_photo(photo_id)
        if p is None:
            raise HTTPException(status_code=404)
        open_in_default_app(p.path)
        return {"ok": True}

    @app.get("/api/settings/ai")
    def get_ai_settings():
        status = _config.public_ai_status()
        prov = get_provider(_config.ai_config())
        status["vision"] = prov.vision if prov else None
        return status

    @app.post("/api/settings/ai")
    def set_ai_settings(body: AiSettings):
        _config.save_ai_config(
            body.provider,
            api_key=body.api_key,
            base_url=body.base_url,
            model=body.model,
        )
        status = _config.public_ai_status()
        prov = get_provider(_config.ai_config())
        status["vision"] = prov.vision if prov else None
        return status

    @app.get("/api/search")
    def search(q: str):
        ids = ai.search(_index(), q)
        if ids is None:
            raise HTTPException(status_code=409, detail="AI not configured")
        return list(ids)

    @app.post("/api/ai/analyze")
    def analyze():
        return {"analyzed": ai.analyze_library(_index())}

    @app.post("/api/reorder")
    def reorder(body: OrderBody):
        _guard_indexing()
        idx = _index()
        byid = {p.id: p for p in idx.all_photos()}
        paths = [byid[i].path for i in body.ordered_ids if i in byid]
        from phota import organize

        n = organize.apply_order(app.state.folder, paths)
        _rebuild()
        return {"renamed": n}

    @app.post("/api/sort")
    def sort(body: SortBody):
        _guard_indexing()
        idx = _index()
        byid = {p.id: p for p in idx.all_photos()}
        paths = [byid[i].path for i in body.ids if i in byid]
        from phota import organize

        try:
            n = organize.sort_into_folder(app.state.folder, body.folder_name, paths)
        except FileExistsError as e:
            raise HTTPException(status_code=409, detail=f"destination conflict: {e}")
        _rebuild()
        return {"moved": n, "folder": organize._safe_name(body.folder_name)}

    @app.post("/api/undo")
    def undo():
        _guard_indexing()
        from phota import organize

        n = organize.undo_last(app.state.folder)
        _rebuild()
        return {"undone": n}

    @app.post("/api/organize")
    def organize_action(body: OrganizeBody):
        from phota import dedupe, organize

        if not app.state.folder:
            raise HTTPException(status_code=400, detail="no active folder")
        _guard_indexing()
        idx = _index()
        photos = idx.all_photos()
        folder = app.state.folder
        action = body.action
        try:
            if action == "sort_by_date":
                ordered = sorted(photos, key=lambda p: (p.captured_at or ""))
                n = organize.apply_order(folder, [p.path for p in ordered])
                result = {"action": action, "renamed": n}
            elif action == "by_day":
                assignments = [
                    ((p.captured_at or "undated")[:10], p.path) for p in photos
                ]
                n, folders = organize.group_into_folders(folder, assignments)
                result = {"action": action, "moved": n, "folders": folders}
            elif action == "by_camera":
                assignments = [((p.camera or "Unknown"), p.path) for p in photos]
                n, folders = organize.group_into_folders(folder, assignments)
                result = {"action": action, "moved": n, "folders": folders}
            elif action == "duplicates":
                groups = dedupe.find_duplicate_groups(idx)
                byid = {p.id: p for p in photos}
                assignments = [
                    ("_duplicates", byid[pid].path)
                    for g in groups
                    for pid in g[1:]
                    if pid in byid
                ]
                if assignments:
                    n, _ = organize.group_into_folders(folder, assignments)
                else:
                    n = 0
                result = {"action": action, "moved": n}
            else:
                raise HTTPException(status_code=400, detail="unknown action")
        except FileExistsError as e:
            raise HTTPException(status_code=409, detail=str(e))
        _rebuild()
        return result

    @app.post("/api/rename")
    def rename(body: RenameBody):
        from phota import organize
        from phota.rename import plan_renames

        if not app.state.folder:
            raise HTTPException(status_code=400, detail="no active folder")
        _guard_indexing()
        photos = _index().all_photos()
        try:
            plan = plan_renames(photos, body.fmt, body.word)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if body.dry_run:
            return {
                "total": len(plan),
                "examples": [
                    {"from": os.path.basename(src), "to": new}
                    for src, new in plan[:3]
                ],
            }
        try:
            n = organize.rename_files(app.state.folder, plan)
        except FileExistsError as e:
            raise HTTPException(status_code=409, detail=str(e))
        _rebuild()
        return {"renamed": n}

    @app.get("/api/duplicates")
    def duplicates():
        from phota import dedupe

        return [
            {"ids": g, "keeper": g[0]}
            for g in dedupe.find_duplicate_groups(_index())
        ]

    # Mount the built SPA LAST so it does not shadow the /api routes above.
    # Conditional on the build existing so tests/dev without a build still run.
    from fastapi.staticfiles import StaticFiles

    _dist = Path(__file__).resolve().parent.parent / "web" / "dist"
    if _dist.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(_dist), html=True),
            name="spa",
        )

    return app
