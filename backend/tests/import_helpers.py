"""Shortcuts for sending the fixture files through the import steps."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"

# Column matching for the fixture files: column index -> field.
PARTS_MAPPING = {
    0: "sku", 1: "name", 2: "brand", 3: "category", 4: "oem_reference", 5: "unit_cost",
    6: "sale_price", 7: "min_stock", 8: "quantity", 9: "branch", 10: "supplier",
}
SALES_MAPPING = {0: "date", 1: "sku", 2: "quantity", 3: "unit_price", 4: "branch"}


class Answer:
    """What the steps ended with, shaped like one response: the summary, or the problem."""

    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self.body = body
        self.text = json.dumps(body)

    def json(self) -> dict:
        return self.body


def upload(browser: TestClient, kind: str, file_name: str, content: bytes | None = None):
    body = content if content is not None else (FIXTURES / file_name).read_bytes()
    return browser.post("/api/imports/upload", data={"kind": kind}, files={"file": (file_name, body)})


def send(browser: TestClient, step: str, kind: str, file_name: str, mapping: dict | None = None, content: bytes | None = None):
    """Takes a file up to `step` the way the screen does: "preview", "check" or "save"."""
    uploaded = upload(browser, kind, file_name, content)
    if uploaded.status_code != 200 or step == "preview":
        return Answer(uploaded.status_code, uploaded.json().get("preview", uploaded.json()))
    job_id = uploaded.json()["id"]
    checked = browser.post(f"/api/imports/{job_id}/check", json={"mapping": mapping})
    if checked.status_code != 202:
        return checked
    if step == "save" and _current(browser)["status"] == "checked":
        saved = browser.post(f"/api/imports/{job_id}/save")
        assert saved.status_code == 202, saved.text
    job = _current(browser)
    if job["status"] == "failed":
        return Answer(422, {"detail": job["error"]})
    return Answer(200, job["summary"])


def _current(browser: TestClient) -> dict:
    return browser.get("/api/imports/current").json()


def import_parts(browser: TestClient, file_name: str = "parts_fr_messy.xlsx") -> dict:
    response = send(browser, "save", "parts", file_name, PARTS_MAPPING)
    assert response.status_code == 200, response.text
    return response.json()


def import_sales(browser: TestClient, file_name: str = "sales_fr_messy.csv") -> dict:
    response = send(browser, "save", "sales", file_name, SALES_MAPPING)
    assert response.status_code == 200, response.text
    return response.json()
