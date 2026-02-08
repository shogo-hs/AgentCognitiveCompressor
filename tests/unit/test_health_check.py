from acc.application.use_cases.health_check import current_status


def test_current_status_returns_ready() -> None:
    assert current_status() == "ready"
