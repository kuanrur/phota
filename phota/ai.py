from __future__ import annotations

import base64
import json
import os

from phota.index import Index
from phota.models import Photo
from phota.preview import load_preview

_HAS_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))
_MODEL = "claude-opus-4-8"


def _analyze_image(path: str) -> dict | None:
    """Call Claude vision on a downscaled preview. Returns structured tags."""
    import io

    from PIL import Image
    import anthropic

    gray = load_preview(path)
    if gray is None:
        return None
    buf = io.BytesIO()
    Image.fromarray(gray).convert("RGB").save(buf, format="JPEG")
    b64 = base64.standard_b64encode(buf.getvalue()).decode()

    try:
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=_MODEL,
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text":
                        "Return JSON only: {\"caption\": str, \"tags\": [str], "
                        "\"subjects\": [str], \"aesthetic_score\": float 0..1}."},
                ],
            }],
        )
        text = msg.content[0].text
        return json.loads(text)
    except Exception:
        return None


def _cached_analysis(photo: Photo) -> dict | None:
    idx = Index()
    idx.init_schema()
    row = idx.conn.execute(
        "SELECT caption, tags, subjects, aesthetic_score FROM ai WHERE photo_id=?",
        (photo.id,),
    ).fetchone()
    if row:
        return {
            "caption": row["caption"],
            "tags": json.loads(row["tags"] or "[]"),
            "subjects": json.loads(row["subjects"] or "[]"),
            "aesthetic_score": row["aesthetic_score"],
        }
    try:
        result = _analyze_image(photo.path)
    except Exception:
        return None
    if result is None:
        return None
    idx.conn.execute(
        "INSERT OR REPLACE INTO ai "
        "(photo_id, caption, tags, subjects, aesthetic_score, ai_model, analyzed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        (photo.id, result["caption"], json.dumps(result["tags"]),
         json.dumps(result["subjects"]), result["aesthetic_score"], _MODEL),
    )
    idx.conn.commit()
    return result


def rank_with_ai(photos: list[Photo]) -> list[Photo]:
    """Attach an _aesthetic attribute used by cull as a tie-breaker."""
    if not _HAS_KEY:
        return photos
    for p in photos:
        analysis = _cached_analysis(p)
        p._aesthetic = analysis["aesthetic_score"] if analysis else 0.0
    return photos


def semantic_match(photos: list[Photo], query: str) -> set[str] | None:
    """Return ids whose caption/tags contain the query. None if no AI."""
    if not _HAS_KEY:
        return None
    q = query.lower()
    matched = set()
    for p in photos:
        analysis = _cached_analysis(p)
        if not analysis:
            continue
        haystack = (analysis["caption"] or "").lower() + " " + " ".join(
            analysis["tags"]).lower()
        if q in haystack:
            matched.add(p.id)
    return matched
