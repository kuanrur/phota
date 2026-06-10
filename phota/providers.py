from __future__ import annotations

import base64
import io
import json

import httpx

from phota.thumbs import _load_color

PROMPT = (
    'Return ONLY a JSON object describing this photo: '
    '{"caption": str, "tags": [str], "subjects": [str], '
    '"aesthetic_score": float between 0 and 1}.'
)


def _post_json(url, headers, payload):
    r = httpx.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def _encode_b64(path) -> str | None:
    img = _load_color(path)
    if img is None:
        return None
    img.thumbnail((512, 512))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return base64.standard_b64encode(buf.getvalue()).decode()


def _parse(text) -> dict | None:
    data = None
    try:
        data = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start:end + 1])
            except Exception:
                data = None
    if not isinstance(data, dict):
        return None
    return {
        "caption": data.get("caption"),
        "tags": data.get("tags", []),
        "subjects": data.get("subjects", []),
        "aesthetic_score": data.get("aesthetic_score"),
    }


class AnthropicProvider:
    def __init__(self, api_key, model="claude-opus-4-8"):
        self.api_key = api_key
        self.model = model
        self.vision = True

    def available(self):
        return bool(self.api_key)

    def analyze_image(self, path):
        b64 = _encode_b64(path)
        if b64 is None:
            return None
        try:
            resp = _post_json(
                "https://api.anthropic.com/v1/messages",
                {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                {
                    "model": self.model,
                    "max_tokens": 400,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64,
                            }},
                            {"type": "text", "text": PROMPT},
                        ],
                    }],
                },
            )
            return _parse(resp["content"][0]["text"])
        except Exception:
            return None


class OpenAIProvider:
    def __init__(self, api_key, model="gpt-4o"):
        self.api_key = api_key
        self.model = model
        self.vision = True

    def available(self):
        return bool(self.api_key)

    def analyze_image(self, path):
        b64 = _encode_b64(path)
        if b64 is None:
            return None
        try:
            resp = _post_json(
                "https://api.openai.com/v1/chat/completions",
                {
                    "Authorization": f"Bearer {self.api_key}",
                    "content-type": "application/json",
                },
                {
                    "model": self.model,
                    "max_tokens": 400,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PROMPT},
                            {"type": "image_url", "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                            }},
                        ],
                    }],
                },
            )
            return _parse(resp["choices"][0]["message"]["content"])
        except Exception:
            return None


class LocalOpenAIProvider:
    def __init__(self, base_url, model="llava", vision=True):
        self.base_url = base_url
        self.model = model
        self.vision = vision

    def available(self):
        return bool(self.base_url)

    def analyze_image(self, path):
        b64 = _encode_b64(path)
        if b64 is None:
            return None
        try:
            resp = _post_json(
                self.base_url.rstrip("/") + "/chat/completions",
                {"content-type": "application/json"},
                {
                    "model": self.model,
                    "max_tokens": 400,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PROMPT},
                            {"type": "image_url", "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                            }},
                        ],
                    }],
                },
            )
            return _parse(resp["choices"][0]["message"]["content"])
        except Exception:
            return None


def get_provider(cfg):
    if not cfg or not cfg.get("provider"):
        return None
    prov = cfg["provider"]
    if prov == "anthropic":
        return AnthropicProvider(cfg.get("api_key"), cfg.get("model") or "claude-opus-4-8")
    if prov == "openai":
        return OpenAIProvider(cfg.get("api_key"), cfg.get("model") or "gpt-4o")
    if prov == "local":
        return LocalOpenAIProvider(cfg.get("base_url"), cfg.get("model") or "llava", cfg.get("vision", True))
    return None
