"""Production mode: no developer pages, the built website on the same port, no demo data by mistake."""

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.config
import app.main
from app.demo import production_guard
from app.website import serve_website


def test_demo_commands_refuse_to_run_in_production_unless_asked(monkeypatch):
    monkeypatch.setattr(production_guard, "IS_PRODUCTION", True)
    with pytest.raises(SystemExit) as stopped:
        production_guard.refuse_demo_in_production([])
    assert "real shop's computer" in str(stopped.value)

    production_guard.refuse_demo_in_production(["--yes-demo-in-production"])  # on purpose: runs
    monkeypatch.setattr(production_guard, "IS_PRODUCTION", False)
    production_guard.refuse_demo_in_production([])  # while developing: runs


def test_production_has_no_api_docs(monkeypatch):
    monkeypatch.setattr(app.config, "IS_PRODUCTION", True)
    try:
        client = TestClient(importlib.reload(app.main).app)
        for address in ("/api/docs", "/api/openapi.json", "/redoc"):
            assert client.get(address).status_code == 404, address
    finally:
        monkeypatch.undo()
        importlib.reload(app.main)
    assert TestClient(app.main.app).get("/api/docs").status_code == 200  # still there while developing


def test_the_built_website_is_served_with_the_api(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc.js").write_text("console.log(1)")
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    website = FastAPI()

    @website.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    serve_website(website, tmp_path)
    client = TestClient(website)

    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/assets/index-abc.js").text == "console.log(1)"
    assert client.get("/favicon.svg").text == "<svg/>"
    for page in ("/", "/stock", "/orders/purchase-orders/1/print", "/design"):
        answer = client.get(page)
        assert answer.text == "<div id=root></div>" and answer.headers["cache-control"] == "no-cache", page
    assert client.get("/api/nothing-here").status_code == 404
