from phota.models import Photo, Plan, PlanOp
from phota.output import summarize_photos, plan_summary


def test_summarize_photos_counts():
    photos = [
        Photo(id="a", path="/a", filename="a.jpg", kind="jpeg",
              captured_at="2025-12-18T00:15:00", camera="X-T5", series_id=0),
        Photo(id="b", path="/b", filename="b.cr3", kind="raw",
              captured_at="2025-03-21T00:00:00", camera="EOS", series_id=1),
    ]
    s = summarize_photos(photos)
    assert s["count"] == 2
    assert s["series"] == 2
    assert set(s["cameras"]) == {"X-T5", "EOS"}
    assert s["date_range"] == ("2025-03-21", "2025-12-18")


def test_plan_summary_text():
    plan = Plan(name="cull", ops=[PlanOp("copy", "/a", "/out/a", "id")])
    text = plan_summary(plan)
    assert "cull" in text
    assert "1" in text
