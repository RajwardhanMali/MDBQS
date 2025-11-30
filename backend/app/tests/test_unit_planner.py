from app.services.planner import plan


def test_plan_returns_steps():
    result = plan("select *")
    assert isinstance(result, dict)
    assert "plan" in result
