from __future__ import annotations

import json
import shutil
from pathlib import Path

from phota.models import Plan


def save_plan(plan: Plan, path: str) -> None:
    Path(path).write_text(json.dumps(plan.to_dict(), indent=2))


def load_plan(path: str) -> Plan:
    return Plan.from_dict(json.loads(Path(path).read_text()))


def apply_plan(plan: Plan, mode: str = "copy") -> dict:
    """Execute a plan. mode in {copy, symlink, move}.

    Refuses to overwrite existing destinations. Returns a manifest that
    records every executed op so a move can be reversed.
    """
    manifest = {"name": plan.name, "mode": mode, "ops": []}
    for op in plan.ops:
        src = Path(op.src)
        dst = Path(op.dst)
        if dst.exists():
            raise FileExistsError(f"refusing to overwrite {dst}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        action = "move" if mode == "move" else op.action
        if action == "copy":
            shutil.copy2(src, dst)
        elif action == "symlink":
            dst.symlink_to(src.resolve())
        elif action == "move":
            shutil.move(str(src), str(dst))
        else:
            raise ValueError(f"unknown action {action}")
        manifest["ops"].append({"action": action, "src": str(src), "dst": str(dst)})
    return manifest


def reverse_manifest(manifest: dict) -> None:
    """Undo a move manifest by moving files back."""
    if manifest.get("mode") != "move":
        return
    for op in reversed(manifest["ops"]):
        shutil.move(op["dst"], op["src"])
