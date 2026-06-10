from phota.models import Photo, PlanOp, Plan


def test_photo_defaults():
    p = Photo(id="abc", path="/x/a.jpg", filename="a.jpg", kind="jpeg")
    assert p.series_id is None
    assert p.sharpness is None
    assert p.error is None


def test_plan_roundtrips_json():
    plan = Plan(
        name="cull",
        ops=[PlanOp(action="copy", src="/x/a.jpg", dst="/out/a.jpg", photo_id="abc")],
    )
    data = plan.to_dict()
    back = Plan.from_dict(data)
    assert back.name == "cull"
    assert back.ops[0].action == "copy"
    assert back.ops[0].photo_id == "abc"
