import re

from fastapi.testclient import TestClient

from app.api import health
from app.config import APP_URL
from app.main import app


def test_an_unexpected_crash_never_shows_a_stack_trace(monkeypatch, caplog):
    def boom(_session=None):
        raise RuntimeError("something nobody expected")

    monkeypatch.setattr(health, "database_is_reachable", boom)
    # The TestClient re-raises a server's own exceptions by default (handy for most tests); here
    # the crash itself is the point, so this one client is told to behave like a real browser.
    browser = TestClient(app, headers={"Origin": APP_URL}, raise_server_exceptions=False)

    response = browser.get("/api/health")

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert re.fullmatch(r"Something went wrong on our side\. Reference: [0-9A-F]{6}", detail)
    code = detail.split(": ")[1]
    assert any(code in record.getMessage() for record in caplog.records)
