from __future__ import annotations
import json
from phota import config
from phota.providers import get_provider
from phota.index import Index


def _provider():
    return get_provider(config.ai_config())


def _cached(idx, photo_id):
    row = idx.conn.execute('SELECT caption, tags, subjects, aesthetic_score FROM ai WHERE photo_id=?', (photo_id,)).fetchone()
    if not row:
        return None
    return {'caption': row['caption'], 'tags': json.loads(row['tags'] or '[]'), 'subjects': json.loads(row['subjects'] or '[]'), 'aesthetic_score': row['aesthetic_score']}


def analyze(idx, photo):
    prov = _provider()
    if prov is None:
        return None
    cached = _cached(idx, photo.id)
    if cached is not None:
        return cached
    result = prov.analyze_image(photo.path)
    if result is None:
        return None
    cfg = config.ai_config() or {}
    idx.conn.execute(
        'INSERT OR REPLACE INTO ai (photo_id, caption, tags, subjects, aesthetic_score, ai_model, analyzed_at) '
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        (photo.id, result.get('caption'), json.dumps(result.get('tags', [])), json.dumps(result.get('subjects', [])), result.get('aesthetic_score'), cfg.get('provider')))
    idx.conn.commit()
    return result


def analyze_library(idx, limit=None):
    if _provider() is None:
        return 0
    count = 0
    for p in idx.all_photos():
        if _cached(idx, p.id) is None and analyze(idx, p) is not None:
            count += 1
            if limit and count >= limit:
                break
    return count


def search(idx, query):
    if _provider() is None:
        return None
    q = query.lower()
    matched = set()
    for row in idx.conn.execute('SELECT photo_id, caption, tags FROM ai').fetchall():
        hay = ((row['caption'] or '') + ' ' + (row['tags'] or '')).lower()
        if q in hay:
            matched.add(row['photo_id'])
    return matched


def rank_with_ai(photos):
    if _provider() is None:
        return photos
    idx = Index(); idx.init_schema()
    for p in photos:
        a = analyze(idx, p)
        p._aesthetic = a['aesthetic_score'] if a else 0.0
    return photos


def semantic_match(photos, query):
    if _provider() is None:
        return None
    idx = Index(); idx.init_schema()
    q = query.lower(); matched = set()
    for p in photos:
        a = analyze(idx, p)
        if not a:
            continue
        hay = ((a.get('caption') or '') + ' ' + ' '.join(a.get('tags') or [])).lower()
        if q in hay:
            matched.add(p.id)
    return matched
