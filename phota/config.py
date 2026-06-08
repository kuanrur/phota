from pathlib import Path

# Index location. Overridable in tests via PHOTA_DB env var.
import json
import os


def db_path() -> Path:
    override = os.environ.get("PHOTA_DB")
    if override:
        return Path(override)
    return Path.home() / ".phota" / "index.db"


def config_path() -> Path:
    """Config file lives next to the db so tests isolate via PHOTA_DB."""
    return Path(db_path()).parent / "config.json"


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_ai_config(provider, api_key=None, base_url=None, model=None):
    cfg = load_config()
    cfg["ai"] = {
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
    }
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg))
    os.chmod(path, 0o600)


def ai_config():
    """Raw AI config including api_key. Use only to call the provider."""
    return load_config().get("ai")


def public_ai_status() -> dict:
    """Safe status for API/UI: never exposes the api_key."""
    cfg = ai_config()
    if not cfg or not cfg.get("provider"):
        return {"configured": False, "provider": None}
    return {"configured": True, "provider": cfg["provider"]}


# Burst grouping: photos within this many seconds belong to the same series.
SERIES_GAP_SECONDS = 3
# Event grouping: gaps larger than this start a new event.
EVENT_GAP_SECONDS = 3 * 60 * 60
# Perceptual-hash distance below which two photos are "visually similar".
PHASH_SIMILAR_DISTANCE = 10
# Image extensions we recognize.
JPEG_EXTS = {".jpg", ".jpeg"}
RAW_EXTS = {".cr3", ".cr2", ".nef", ".arw", ".raf"}
TIFF_EXTS = {".tif", ".tiff"}
IMAGE_EXTS = JPEG_EXTS | RAW_EXTS | TIFF_EXTS
