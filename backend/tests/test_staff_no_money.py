"""A sweep across the whole app: staff must never see money, anywhere (CLAUDE.md "staff never
get money"). The feature tests next to each screen (test_today.py, test_orders.py,
test_purchase_orders.py, test_parts.py) check exact fields; this one is the safety net for a
future GET endpoint nobody remembered to gate -- it calls every one of them as staff and fails
if a money-shaped key shows up anywhere in the JSON."""

import re

from fastapi.routing import APIRoute

from app.main import app


def api_routes() -> list[APIRoute]:
    """Every APIRoute of the app, however deep `include_router` nested it (FastAPI wraps each
    included router in its own object instead of flattening them into `app.routes`)."""
    found: list[APIRoute] = []

    def walk(routes) -> None:
        for route in routes:
            if isinstance(route, APIRoute):
                found.append(route)
            elif hasattr(route, "original_router"):  # fastapi.routing._IncludedRouter
                walk(route.original_router.routes)
            elif hasattr(route, "routes"):  # a plain APIRouter
                walk(route.routes)

    walk(app.routes)
    return found
from tests.helpers import add_member, member_with_own_password, set_up_shop
from tests.test_orders import shop_id
from tests.test_purchase_orders import one_suggestion

MONEY_KEY = re.compile(r"cost|price|margin|money|dirham|budget", re.IGNORECASE)

# Not JSON on success (a file download): checked by hand in test_imports.py / test_exports.py instead.
SKIPPED_PATHS = {"/api/imports/sample", "/api/exports/data"}


def money_leaks(value, path: str = "") -> list[str]:
    """Every dict key under `value` that looks like a money field, as "a.b.c" paths."""
    found = []
    if isinstance(value, dict):
        for key, inner in value.items():
            here = f"{path}.{key}" if path else key
            if MONEY_KEY.search(key):
                found.append(here)
            found += money_leaks(inner, here)
    elif isinstance(value, list):
        for index, inner in enumerate(value):
            found += money_leaks(inner, f"{path}[{index}]")
    return found


def test_staff_sees_no_money_on_any_get_endpoint(browser):
    """Seeds one of everything that carries money (a suggestion, an approved line, a purchase
    order), logs in as staff, and calls every GET route the app has."""
    set_up_shop(browser)
    shop_id()  # makes sure the shop exists before seeding
    part_id, line = one_suggestion(browser, sku="OIL-1", per_week=9, on_hand=6)
    browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve"})
    [po] = browser.get("/api/orders/purchase-orders").json()
    run = browser.get("/api/orders/suggestions/latest").json()
    [group] = run["groups"]

    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")

    path_values = {"part_id": str(part_id), "po_id": po["id"], "run_id": run["id"]}

    checked = 0
    for route in api_routes():
        if "GET" not in route.methods or not route.path.startswith("/api"):
            continue
        if route.path in SKIPPED_PATHS:
            continue
        path = route.path
        for name, value in path_values.items():
            path = path.replace("{" + name + "}", value)
        assert "{" not in path, f"test_staff_no_money.py doesn't know how to fill {route.path}"

        params = {"group": group["key"]} if path.endswith("/lines") else {}
        response = staff.get(path, params=params)
        checked += 1
        if response.status_code != 200:
            continue  # staff isn't allowed here at all (403/422): nothing of this call leaked
        leaks = money_leaks(response.json())
        assert leaks == [], f"{path} leaks money to staff: {leaks}"

    assert checked >= 20  # every GET route the app had when this test was written
