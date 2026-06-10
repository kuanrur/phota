from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Photo:
    id: str
    path: str
    filename: str
    kind: str  # "jpeg" | "raw" | "tiff"
    size: int = 0
    mtime: float = 0.0
    captured_at: Optional[str] = None  # ISO 8601 string
    captured_approx: bool = False
    camera: Optional[str] = None
    lens: Optional[str] = None
    iso: Optional[int] = None
    shutter: Optional[str] = None
    aperture: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    sharpness: Optional[float] = None
    exposure_score: Optional[float] = None
    phash: Optional[str] = None
    series_id: Optional[int] = None
    error: Optional[str] = None
    analyzed_at: Optional[str] = None
    keep: Optional[int] = None


@dataclass
class PlanOp:
    action: str  # "copy" | "symlink" | "move"
    src: str
    dst: str
    photo_id: str


@dataclass
class Plan:
    name: str
    ops: list[PlanOp] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "ops": [asdict(op) for op in self.ops]}

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        return cls(
            name=data["name"],
            ops=[PlanOp(**op) for op in data["ops"]],
        )
