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


def send(browser: TestClient, step: str, kind: str, file_name: str, mapping: dict | None = None, content: bytes | None = None):
    data = {"kind": kind}
    if mapping is not None:
        data["mapping"] = json.dumps(mapping)
    body = content if content is not None else (FIXTURES / file_name).read_bytes()
    return browser.post(f"/api/imports/{step}", data=data, files={"file": (file_name, body)})


def import_parts(browser: TestClient, file_name: str = "parts_fr_messy.xlsx") -> dict:
    response = send(browser, "save", "parts", file_name, PARTS_MAPPING)
    assert response.status_code == 200, response.text
    return response.json()


def import_sales(browser: TestClient, file_name: str = "sales_fr_messy.csv") -> dict:
    response = send(browser, "save", "sales", file_name, SALES_MAPPING)
    assert response.status_code == 200, response.text
    return response.json()
