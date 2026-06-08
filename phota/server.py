from __future__ import annotations

from collections import defaultdict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from phota import store, thumbs
from phota.index import Index
from phota.output import summarize_photos


def _index() -> Index:
    idx = Index()
    idx.init_schema()
    return idx


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

    return app
