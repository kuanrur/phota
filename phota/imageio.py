"""Central image-decoding setup.

Importing this module registers the HEIF/HEIC opener with Pillow so that
``PIL.Image.open`` can read iPhone .heic/.heif files anywhere in phota. PNG,
WebP, GIF, BMP and TIFF are handled by Pillow natively. Registration is
idempotent and safe to trigger from multiple import sites.
"""

from __future__ import annotations

try:  # pillow-heif is a hard dependency, but degrade rather than crash scans.
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE = True
except Exception:  # pragma: no cover - only when the wheel is missing
    HEIF_AVAILABLE = False
