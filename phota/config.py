from pathlib import Path

# Index location. Overridable in tests via PHOTA_DB env var.
import os


def db_path() -> Path:
    override = os.environ.get("PHOTA_DB")
    if override:
        return Path(override)
    return Path.home() / ".phota" / "index.db"


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
