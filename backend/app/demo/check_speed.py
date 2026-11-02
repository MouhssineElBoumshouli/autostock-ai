"""Times every page the way the website calls it: each request 20 times, the typical time (median)
and the slowest. Meant for the big test shop (app/demo/big_shop.py) on the production stack.

Run from a container on the same Docker network as the app, for example:
  docker compose -f docker-compose.prod.yml run --rm -e CHECK_PASSWORD=... app \
      python -m app.demo.check_speed --url http://app:8000 --email big@autostock.local
Add --while-forecasting to start a forecast run and time a few pages while it runs, or --actions to
also time the order buttons (this adds order suggestions and a purchase order to the shop).
"""

import argparse
import http.cookiejar
import json
import os
import statistics
import urllib.parse
import urllib.request
from time import perf_counter, sleep

TRIES = 20
TOO_SLOW = 30  # seconds: a page this slow is tried only FEW_TRIES times
FEW_TRIES = 3
SEARCHES = [
    "filtre a huile logan",
    "plaquettes de frein avant",
    "amortisseur",
    "bougie",
    "batterie 70ah",
    "kit embrayage clio",
    "demareur",  # a typo
    "huile 5w30",
    "BIG-01234",
]  # plus one OEM number, read from the shop
QUESTIONS = [
    "How many oil filters did we sell last month?",
    "what are our best sellers this month?",
    "whats running out?",
    "What should I order and how much will it cost?",
    "how many alternators do we have in stock",
]


class Site:
    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[float, bytes]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.url + path, data=data, method=method)
        request.add_header("Origin", self.url)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        started = perf_counter()
        with self.opener.open(request, timeout=600) as response:
            content = response.read()
        return perf_counter() - started, content

    def json(self, method: str, path: str, body: dict | None = None):
        return json.loads(self.call(method, path, body)[1] or b"null")


def timed(site: Site, label: str, method: str, path: str, body: dict | None = None, tries: int = TRIES) -> tuple[str, float, float]:
    times = []
    while len(times) < tries:
        times.append(site.call(method, path, body)[0])
        if len(times) == FEW_TRIES and min(times) > TOO_SLOW:
            break  # minutes per try: a few tries tell the story
    result = (label, statistics.median(times), max(times))
    note = f"   (only {len(times)} tries)" if len(times) < tries else ""
    print(f"{label:45} typical {result[1]:7.3f} s   slowest {result[2]:7.3f} s{note}", flush=True)
    return result


def check_pages(site: Site, email: str, password: str, tries: int = TRIES) -> list[tuple[str, float, float]]:
    login = {"email": email, "password": password}
    results = [timed(site, "Login", "POST", "/api/auth/login", login, tries)]
    first_page = site.json("GET", "/api/stock/parts")["items"]
    part_id = first_page[0]["id"]
    branch = site.json("GET", "/api/stock/filters")["branches"][0]["id"]
    oem = site.json("GET", f"/api/parts/{part_id}").get("oem_reference") or "0000"
    run = site.json("GET", "/api/orders/suggestions/latest")
    pages = [
        ("Today", "/api/today"),
        ("Stock: cards", "/api/stock/summary"),
        ("Stock: filter choices", "/api/stock/filters"),
        ("Stock: first page", "/api/stock/parts"),
        ("Stock: filter Low stock", "/api/stock/parts?status=low"),
        ("Stock: filter Dead stock", "/api/stock/parts?status=dead"),
        ("Stock: filter category + branch", f"/api/stock/parts?category=Brakes&branch={branch}"),
        ("Stock: filter Running out", "/api/stock/parts?running_out=true"),
        ("Stock: sort by runs out", "/api/stock/parts?sort=runs_out_days"),
        ("Stock: sort by quantity, page 40", "/api/stock/parts?sort=quantity&direction=desc&page=40"),
        ("Part panel: details", f"/api/parts/{part_id}"),
        ("Part panel: forecast", f"/api/forecasts/part/{part_id}"),
        ("What to order (latest run)", "/api/orders/suggestions/latest"),
        ("Purchase orders", "/api/orders/purchase-orders"),
        ("Alerts", "/api/alerts"),
        ("Settings", "/api/settings"),
        ("Settings: backups", "/api/backups"),
    ]
    orders = site.json("GET", "/api/orders/purchase-orders")
    if orders:
        pages.append(("Purchase order panel", f"/api/orders/purchase-orders/{orders[0]['id']}"))
    results += [timed(site, label, "GET", path, tries=tries) for label, path in pages]
    for words in [*SEARCHES, oem]:
        results.append(timed(site, f"Search: {words}", "GET", "/api/stock/parts?" + urllib.parse.urlencode({"search": words}), tries=tries))
    for question in QUESTIONS:
        results.append(timed(site, f"Ask: {question[:38]}", "POST", "/api/ask", {"question": question}, tries))
    results.append(timed(site, "Excel export", "GET", "/api/exports/data", tries=tries))
    if run is None:
        print("(No order suggestions yet: 'What to order' timed an empty page.)")
    return results


def check_actions(site: Site) -> None:
    """The heavy buttons: "Make new suggestions" (What to order), then "Approve all" for the
    supplier with the fewest lines, so the shop has a purchase order to show."""
    timed(site, "Make order suggestions (button)", "POST", "/api/orders/suggestions", {}, 1)
    run = site.json("GET", "/api/orders/suggestions/latest")
    lines = {}
    for line in run["lines"]:
        if line["supplier_id"] and line["status"] == "suggested":
            lines[line["supplier_id"]] = lines.get(line["supplier_id"], 0) + 1
    supplier = min(lines, key=lines.get)
    timed(site, f"Approve all ({lines[supplier]} lines)", "POST", f"/api/orders/runs/{run['id']}/suppliers/{supplier}/approve-all", {}, 1)


def check_while_forecasting(site: Site, tries: int) -> None:
    """Starts a forecast run and times a few pages until it is done."""
    before = site.json("GET", "/api/forecasts/runs/latest")
    site.call("POST", "/api/forecasts/run", {})
    started = perf_counter()
    rounds = 0
    while True:
        latest = site.json("GET", "/api/forecasts/runs/latest")
        if latest and (before is None or latest["created_at"] != before["created_at"]):
            break
        for label, path in [("Today", "/api/today"), ("Stock: first page", "/api/stock/parts"),
                            ("Search: amortisseur", "/api/stock/parts?search=amortisseur")]:
            timed(site, f"(forecast running) {label}", "GET", path, tries=tries)
        rounds += 1
        sleep(5)
    print(f"Forecast run: {latest['status']}, {latest['seconds']:.0f} s for {latest['series_count']:,} part-branch pairs "
          f"(seen done after {perf_counter() - started:.0f} s, {rounds} rounds of page checks).")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://app:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--tries", type=int, default=TRIES)
    parser.add_argument("--while-forecasting", action="store_true")
    parser.add_argument("--actions", action="store_true", help="time the order buttons first (changes the shop's data)")
    args = parser.parse_args()
    site = Site(args.url)
    site.call("POST", "/api/auth/login", {"email": args.email, "password": os.environ["CHECK_PASSWORD"]})
    if args.while_forecasting:
        check_while_forecasting(site, tries=3)
        return
    if args.actions:
        check_actions(site)
    check_pages(site, args.email, os.environ["CHECK_PASSWORD"], args.tries)


if __name__ == "__main__":
    main()
