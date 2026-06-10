from __future__ import annotations


def set_keep(idx, photo_id, keep) -> None:
    if keep is None:
        value = None
    else:
        value = 1 if keep else 0
    idx.conn.execute("UPDATE photos SET keep=? WHERE id=?", (value, photo_id))
    idx.conn.commit()


def get_keep(idx, photo_id):
    row = idx.conn.execute("SELECT keep FROM photos WHERE id=?", (photo_id,)).fetchone()
    if row is None or row["keep"] is None:
        return None
    return bool(row["keep"])


def create_album(idx, name) -> None:
    idx.conn.execute("INSERT OR IGNORE INTO albums (name) VALUES (?)", (name,))
    idx.conn.commit()


def list_albums(idx) -> list[dict]:
    rows = idx.conn.execute(
        "SELECT a.name AS name, "
        "(SELECT COUNT(*) FROM album_photos ap WHERE ap.album = a.name) AS count "
        "FROM albums a ORDER BY a.name"
    ).fetchall()
    return [{"name": r["name"], "count": r["count"]} for r in rows]


def delete_album(idx, name) -> None:
    idx.conn.execute("DELETE FROM albums WHERE name=?", (name,))
    idx.conn.execute("DELETE FROM album_photos WHERE album=?", (name,))
    idx.conn.commit()


def add_to_album(idx, name, ids) -> None:
    create_album(idx, name)
    for pid in ids:
        idx.conn.execute(
            "INSERT OR IGNORE INTO album_photos (album, photo_id) VALUES (?, ?)",
            (name, pid),
        )
    idx.conn.commit()


def remove_from_album(idx, name, ids) -> None:
    for pid in ids:
        idx.conn.execute(
            "DELETE FROM album_photos WHERE album=? AND photo_id=?",
            (name, pid),
        )
    idx.conn.commit()


def albums_for(idx, photo_id) -> list[str]:
    rows = idx.conn.execute(
        "SELECT album FROM album_photos WHERE photo_id=? ORDER BY album",
        (photo_id,),
    ).fetchall()
    return [r["album"] for r in rows]


def photos_in_album(idx, name) -> list[str]:
    rows = idx.conn.execute(
        "SELECT photo_id FROM album_photos WHERE album=? ORDER BY photo_id",
        (name,),
    ).fetchall()
    return [r["photo_id"] for r in rows]
