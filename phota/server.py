from __future__ import annotations

import os
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


class OrderBody(BaseModel):
    ordered_ids: list[str]


class SortBody(BaseModel):
    folder_name: str
    ids: list[str]


def reveal_in_finder(path):
    import subprocess

    subprocess.run(["open", "-R", path])


def open_in_default_app(path):
    import subprocess

    subprocess.run(["open", path])


def list_finder_folders():
    """Return POSIX paths of folders currently open in Finder windows."""
    import subprocess

    script = 'tell application "Finder"\nset out to ""\nrepeat with w in (every Finder window)\ntry\nset out to out & (POSIX path of (target of w as alias)) & linefeed\nend try\nend repeat\nreturn out\nend tell'
    try:
        res = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=5
        )
        return [ln for ln in res.stdout.splitlines() if ln.strip()]
    except Exception:
        return []


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

    def _index() -> Index:
        idx = Index(app.state.db_path)
        idx.init_schema()
        return idx

    @app.get("/api/finder-folders")
    def finder_folders():
        return [
            {"path": p, "name": os.path.basename(p.rstrip("/")) or p}
            for p in list_finder_folders()
        ]

    @app.post("/api/open-folder")
    def open_folder(body: FolderBody):
        folder = os.path.abspath(os.path.expanduser(body.path))
        dbp = str(library_db_path(folder))
        build_index(folder, db_path=dbp)
        app.state.folder = folder
        app.state.db_path = dbp
        return {"folder": folder, "count": len(_index().all_photos())}

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
        idx = _index()
        byid = {p.id: p for p in idx.all_photos()}
        paths = [byid[i].path for i in body.ordered_ids if i in byid]
        from phota import organize

        n = organize.apply_order(app.state.folder, paths)
        build_index(app.state.folder, db_path=app.state.db_path)
        return {"renamed": n}

    @app.post("/api/sort")
    def sort(body: SortBody):
        idx = _index()
        byid = {p.id: p for p in idx.all_photos()}
        paths = [byid[i].path for i in body.ids if i in byid]
        from phota import organize

        n = organize.sort_into_folder(app.state.folder, body.folder_name, paths)
        build_index(app.state.folder, db_path=app.state.db_path)
        return {"moved": n, "folder": organize._safe_name(body.folder_name)}

    @app.post("/api/undo")
    def undo():
        from phota import organize

        n = organize.undo_last(app.state.folder)
        build_index(app.state.folder, db_path=app.state.db_path)
        return {"undone": n}

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
