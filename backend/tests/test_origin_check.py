from fastapi.testclient import TestClient

from app.config import read_addresses
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


SHOP_ADDRESSES = ["http://localhost:8080", "http://192.168.1.20:8080", "http://comptoir-pc:8080"]


def test_every_shop_address_is_allowed_and_another_is_refused(monkeypatch):
    monkeypatch.setattr("app.origin_check.APP_URLS", SHOP_ADDRESSES)

    for origin in ["http://localhost:8080", "http://192.168.1.20:8080", "http://COMPTOIR-PC:8080"]:
        assert TestClient(app, headers={"Origin": origin}).post("/api/setup", json={}).status_code == 422, origin
    for origin in ["http://192.168.1.21:8080", "http://localhost:5173", "https://evil.example"]:
        assert TestClient(app, headers={"Origin": origin}).post("/api/setup", json={}).status_code == 403, origin


def test_addresses_are_read_from_a_comma_separated_list():
    assert read_addresses(" http://localhost:8080 , http://PC-NAME:8080/,, ") == ["http://localhost:8080", "http://pc-name:8080"]
