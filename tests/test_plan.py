import json

from phota.models import Plan, PlanOp
from phota.plan import apply_plan
from tests.fixtures import make_jpeg


def test_apply_copy_leaves_original(tmp_path):
    src = make_jpeg(tmp_path / "a.jpg")
    dst = tmp_path / "out" / "a.jpg"
    plan = Plan(name="t", ops=[PlanOp("copy", str(src), str(dst), "id1")])
    manifest = apply_plan(plan, mode="copy")
    assert dst.exists()
    assert src.exists()  # original untouched
    assert manifest["ops"][0]["action"] == "copy"


def test_apply_move_is_recorded_for_reversal(tmp_path):
    src = make_jpeg(tmp_path / "a.jpg")
    dst = tmp_path / "out" / "a.jpg"
    plan = Plan(name="t", ops=[PlanOp("move", str(src), str(dst), "id1")])
    manifest = apply_plan(plan, mode="move")
    assert dst.exists()
    assert not src.exists()
    assert manifest["ops"][0]["src"] == str(src)
    assert manifest["ops"][0]["dst"] == str(dst)


def test_apply_honors_symlink_action(tmp_path):
    src = make_jpeg(tmp_path / "a.jpg")
    dst = tmp_path / "out" / "a.jpg"
    plan = Plan(name="t", ops=[PlanOp("symlink", str(src), str(dst), "id1")])
    apply_plan(plan, mode="copy")
    assert dst.is_symlink()


def test_apply_refuses_overwrite(tmp_path):
    src = make_jpeg(tmp_path / "a.jpg")
    dst = make_jpeg(tmp_path / "b.jpg")  # already exists
    plan = Plan(name="t", ops=[PlanOp("copy", str(src), str(dst), "id1")])
    try:
        apply_plan(plan, mode="copy")
        assert False, "expected refusal"
    except FileExistsError:
        pass
