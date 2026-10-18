from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import OWNER_PASSWORD, set_up_shop


def test_change_from_another_website_is_rejected(browser):
    set_up_shop(browser)
    evil = TestClient(app, headers={"Origin": "https://evil.example"})

    response = evil.post("/api/auth/login", json={"email": "owner@shop.ma", "password": OWNER_PASSWORD})

    assert response.status_code == 403


def test_change_without_origin_is_rejected():
    no_origin = TestClient(app)

    response = no_origin.post("/api/setup", json={})

    assert response.status_code == 403


def test_reading_works_without_origin():
    assert TestClient(app).get("/api/health").status_code == 200
