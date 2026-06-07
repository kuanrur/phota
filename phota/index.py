from __future__ import annotations

import sqlite3
from dataclasses import fields

from phota.config import db_path
from phota.models import Photo

_PHOTO_COLUMNS = [f.name for f in fields(Photo)]


class Index:
    def __init__(self, path=None):
        self.path = str(path) if path else str(db_path())
        if self.path != ":memory:":
            from pathlib import Path

            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS photos (
                id TEXT PRIMARY KEY,
                path TEXT, filename TEXT, kind TEXT,
                size INTEGER, mtime REAL,
                captured_at TEXT, captured_approx INTEGER,
                camera TEXT, lens TEXT, iso INTEGER,
                shutter TEXT, aperture TEXT,
                gps_lat REAL, gps_lon REAL,
                sharpness REAL, exposure_score REAL,
                phash TEXT, series_id INTEGER,
                error TEXT, analyzed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS ai (
                photo_id TEXT PRIMARY KEY,
                caption TEXT, tags TEXT, subjects TEXT,
                aesthetic_score REAL, ai_model TEXT, analyzed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS pairs (
                raw_id TEXT, jpeg_id TEXT
            );
            """
        )
        self.conn.commit()

    def upsert_photo(self, photo: Photo) -> None:
        cols = ", ".join(_PHOTO_COLUMNS)
        placeholders = ", ".join(f":{c}" for c in _PHOTO_COLUMNS)
        updates = ", ".join(f"{c}=excluded.{c}" for c in _PHOTO_COLUMNS if c != "id")
        data = {c: getattr(photo, c) for c in _PHOTO_COLUMNS}
        data["captured_approx"] = int(photo.captured_approx)
        self.conn.execute(
            f"INSERT INTO photos ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            data,
        )
        self.conn.commit()

    def _row_to_photo(self, row: sqlite3.Row) -> Photo:
        d = dict(row)
        d["captured_approx"] = bool(d["captured_approx"])
        return Photo(**d)

    def get_photo(self, photo_id: str) -> Photo | None:
        row = self.conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
        return self._row_to_photo(row) if row else None

    def all_photos(self) -> list[Photo]:
        rows = self.conn.execute("SELECT * FROM photos ORDER BY captured_at").fetchall()
        return [self._row_to_photo(r) for r in rows]

    def known_mtimes(self) -> dict[str, float]:
        rows = self.conn.execute("SELECT id, mtime FROM photos").fetchall()
        return {r["id"]: r["mtime"] for r in rows}

    def set_series(self, photo_id: str, series_id: int) -> None:
        self.conn.execute("UPDATE photos SET series_id=? WHERE id=?", (series_id, photo_id))
        self.conn.commit()

    def add_pair(self, raw_id: str, jpeg_id: str) -> None:
        self.conn.execute("INSERT INTO pairs (raw_id, jpeg_id) VALUES (?, ?)", (raw_id, jpeg_id))
        self.conn.commit()
