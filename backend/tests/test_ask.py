"""Ask your shop: every question type answered from real data, money hidden from staff, each shop
sees only its own data, and the model is only a reader that falls back to the rule."""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.ai import llm
from app.ask import understand as understand_module
from app.ask.answers import CANNOT_ANSWER_YET
from app.db import SessionLocal
from app.models import AuditLog, Branch, Forecast, Organization, Part, SaleLine, StockLevel
from tests.helpers import OWNER_PASSWORD, add_member, create_other_shop, logged_in_browser, member_with_own_password, set_up_shop
from tests.test_orders import add_part
from tests.test_today import add_alert

LAST_DAY = date(2026, 9, 30)  # the shop's last day with sales: its "today"
MAIN = "Atlas Parts"
RABAT = "Rabat - Agdal"


@pytest.fixture(autouse=True)
def ai_off(monkeypatch):
    monkeypatch.setattr(llm, "is_on", lambda: False)


def shop_named(name: str) -> uuid.UUID:
    with SessionLocal() as db:
        return db.scalar(select(Organization.id).where(Organization.name == name))


def branch_named(organization_id: uuid.UUID, name: str) -> uuid.UUID:
    with SessionLocal() as db:
        found = db.scalar(select(Branch.id).where(Branch.organization_id == organization_id, Branch.name == name))
        if found is None:
            branch = Branch(organization_id=organization_id, name=name)
            db.add(branch)
            db.commit()
            found = branch.id
        return found


def new_part(organization_id: uuid.UUID, name: str, category: str, unit_cost: int = 7000) -> uuid.UUID:
    with SessionLocal() as db:
        part = Part(organization_id=organization_id, sku=f"SKU-{uuid.uuid4().hex[:6]}", name=name, category=category,
                    unit_cost=unit_cost)
        db.add(part)
        db.commit()
        return part.id


def sell(organization_id: uuid.UUID, part_id: uuid.UUID, branch: str, days_ago: int, quantity: int, unit_price: int = 10000):
    with SessionLocal() as db:
        db.add(SaleLine(organization_id=organization_id, part_id=part_id, branch_id=branch_named(organization_id, branch),
                        sold_on=LAST_DAY - timedelta(days=days_ago), quantity=quantity, unit_price=unit_price))
        db.commit()


def shelve(organization_id: uuid.UUID, part_id: uuid.UUID, branch: str, quantity: int, expected_30d: float | None = None):
    with SessionLocal() as db:
        branch_id = branch_named(organization_id, branch)
        db.add(StockLevel(organization_id=organization_id, part_id=part_id, branch_id=branch_id, quantity=quantity))
        if expected_30d is not None:
            db.add(Forecast(organization_id=organization_id, part_id=part_id, branch_id=branch_id, horizon_days=30,
                            history_last_day=LAST_DAY, demand_type="smooth", method="four_week_average",
                            quantity=expected_30d, low=expected_30d / 2, high=expected_30d * 2, backtest_windows=4, reason="test"))
        db.commit()


def ask(browser, question: str) -> dict:
    response = browser.post("/api/ask", json={"question": question})
    assert response.status_code == 200, response.text
    return response.json()


def numbers(answer: dict) -> dict:
    return {number["label"]: number["value"] for number in answer["numbers"]}


@pytest.fixture
def shop(browser) -> uuid.UUID:
    """A shop with oil filters and brake pads sold in two branches."""
    set_up_shop(browser)
    organization_id = shop_named(MAIN)
    oil = new_part(organization_id, "Oil filter", "Filters")
    pads = new_part(organization_id, "Brake pads front", "Brakes")
    sell(organization_id, oil, MAIN, days_ago=0, quantity=3)
    sell(organization_id, oil, RABAT, days_ago=1, quantity=2)
    sell(organization_id, oil, MAIN, days_ago=40, quantity=50)  # long ago
    sell(organization_id, pads, MAIN, days_ago=2, quantity=6, unit_price=30000)
    sell(organization_id, pads, MAIN, days_ago=9, quantity=12, unit_price=30000)  # the week before
    return organization_id


def staff_browser(owner) -> object:
    add_member(owner, "staff@shop.ma", "staff")
    return member_with_own_password("staff@shop.ma")


# One test per question type

def test_sales_of_a_part_with_branch_and_period(browser, shop):
    answer = ask(browser, "how many oil filters did we sell this week")
    assert answer["question_type"] == "sales_of"
    assert answer["filters"] == {"part": "oil filters", "period": "this_week"}
    assert numbers(answer)["Pieces sold"] == 5
    assert numbers(answer)["Sales value"] == 5 * 10000
    assert "5 pieces" in answer["sentence"] and "MAD" in answer["sentence"]

    in_rabat = ask(browser, "oil filters sold this week in rabat")
    assert numbers(in_rabat)["Pieces sold"] == 2


def test_sales_of_a_category(browser, shop):
    answer = ask(browser, "sales of brakes this week")
    assert answer["filters"] == {"category": "Brakes", "period": "this_week"}
    assert numbers(answer)["Pieces sold"] == 6


def test_best_sellers(browser, shop):
    answer = ask(browser, "best sellers this week")
    assert [number["value"] for number in answer["numbers"]] == [6, 5]
    assert answer["sentence"].startswith("Best seller for all parts this week") and "Brake pads front" in answer["sentence"]


def test_sales_vs_the_period_before(browser, shop):
    answer = ask(browser, "brake pads sales compared to last week")
    assert answer["filters"] == {"part": "brake pads", "period": "this_week"}
    assert numbers(answer)["Pieces sold, this period"] == 6
    assert numbers(answer)["Pieces sold, period before"] == 12
    assert "down 50%" in answer["sentence"]


def test_stock_of_a_part_per_branch(browser, shop):
    oil = select_part(shop, "Oil filter")
    shelve(shop, oil, MAIN, 7)
    shelve(shop, oil, RABAT, 4)
    answer = ask(browser, "stock of oil filter")
    assert numbers(answer) == {MAIN: 7, RABAT: 4}
    assert "11 pieces in stock" in answer["sentence"]
    assert numbers(ask(browser, "stock of oil filter in rabat")) == {RABAT: 4}


def test_unknown_words_get_not_sure_and_buttons_instead_of_a_guess(browser, shop):
    answer = ask(browser, "stock of unicorn horns in rabat")
    assert answer["question_type"] == "not_sure"
    assert answer["understood"] is None and answer["numbers"] == []
    assert answer["sentence"] == "I'm not sure what you mean by “unicorn horns”. Did you mean one of these?"
    assert answer["suggestions"][0] == {"question_type": "stock_of_part", "label": f"Stock · {RABAT}"}
    assert len(answer["suggestions"]) == 3

    # The button sends the same question with the type picked: the unknown words are searched as a part.
    picked = browser.post("/api/ask", json={"question": "stock of unicorn horns in rabat", "question_type": "stock_of_part"})
    assert picked.json()["understood"] == f"I understood: Stock of unicorn horns · {RABAT}"
    assert picked.json()["sentence"].startswith("I couldn't find a part")


def test_a_picked_type_must_be_a_real_one(browser, shop):
    for bad in ("drop_tables", "cannot_answer"):
        assert browser.post("/api/ask", json={"question": "x", "question_type": bad}).status_code == 422


def test_every_answer_says_how_the_question_was_read(browser, shop):
    answer = ask(browser, "oil filters sold last month in rabat")
    assert answer["understood"] == f"I understood: Sales of oil filters · {RABAT} · last month"
    assert answer["suggestions"] == []


def test_running_out_uses_the_forecast(browser, shop):
    shelve(shop, select_part(shop, "Oil filter"), MAIN, 10, expected_30d=60)  # 5 days left
    shelve(shop, select_part(shop, "Brake pads front"), MAIN, 1000, expected_30d=60)  # 500 days left
    answer = ask(browser, "what is running out")
    assert numbers(answer)["Parts running out"] == 1
    assert "Oil filter" in answer["sentence"] and "about 5 days" in answer["sentence"]


def test_dead_stock(browser, shop):
    old = new_part(shop, "Radiator", "Cooling", unit_cost=50000)
    sell(shop, old, MAIN, days_ago=120, quantity=1)
    shelve(shop, old, MAIN, 3)
    shelve(shop, select_part(shop, "Oil filter"), MAIN, 9)  # sold this week: not dead
    answer = ask(browser, "dead stock")
    assert numbers(answer)["Dead stock parts"] == 1
    assert numbers(answer)["Value at cost"] == 3 * 50000
    assert "Radiator" in str(answer["numbers"])


def test_forecast_of_a_part(browser, shop):
    shelve(shop, select_part(shop, "Brake pads front"), MAIN, 5, expected_30d=40)
    answer = ask(browser, "forecast for brake pads")
    assert numbers(answer)["Expected, next 30 days"] == 40
    assert numbers(answer)["Likely at least"] == 20
    assert numbers(answer)["Made from sales up to"] == LAST_DAY.isoformat()


def test_what_to_order(browser):
    set_up_shop(browser)
    organization_id = shop_named(MAIN)
    add_part(organization_id, sku="OIL-1", per_week=9, on_hand=6)
    add_part(organization_id, sku="OIL-2", per_week=5, on_hand=1)
    run = browser.post("/api/orders/suggestions", json={}).json()
    answer = ask(browser, "what should I order")
    assert numbers(answer)["Lines to order"] == len(run["lines"]) == 2
    assert numbers(answer)["Total cost"] == sum(line["line_cost"] for line in run["lines"])


def test_open_alerts(browser, shop):
    add_alert(shop, "negative_stock", 100)
    add_alert(shop, "sales_spike", 50)
    add_alert(shop, "sales_drop", 10, status="looked_at")  # reviewed: not open
    answer = ask(browser, "any alerts?")
    assert numbers(answer)["Open alerts"] == 2


def test_late_deliveries_when_there_are_none(browser, shop):
    answer = ask(browser, "which deliveries are late")
    assert answer["question_type"] == "late_deliveries"
    assert answer["sentence"] == "No supplier delivery is late."


@pytest.mark.parametrize("question", ["who is our best customer?", "delete all old parts", "print me an invoice"])
def test_questions_we_cannot_answer_get_no_guess(browser, shop, question):
    answer = ask(browser, question)
    assert answer["question_type"] == "cannot_answer"
    assert answer["sentence"] == CANNOT_ANSWER_YET
    assert answer["numbers"] == [] and answer["understood"] is None


# Permissions, scoping, read-only

def test_staff_get_the_same_answers_without_money(browser, shop):
    old = new_part(shop, "Radiator", "Cooling", unit_cost=50000)
    sell(shop, old, MAIN, days_ago=120, quantity=1)
    shelve(shop, old, MAIN, 3)
    staff = staff_browser(browser)
    for question in ("how many oil filters did we sell this week", "dead stock", "brake pads sales compared to last week"):
        answer = ask(staff, question)
        assert answer["numbers"], question
        assert all(number["unit"] != "money" for number in answer["numbers"]), question
        assert "MAD" not in answer["sentence"], question
    assert numbers(ask(staff, "how many oil filters did we sell this week"))["Pieces sold"] == 5


def test_staff_see_what_to_order_without_its_cost(browser):
    set_up_shop(browser)
    add_part(shop_named(MAIN), sku="OIL-1", per_week=9, on_hand=6)
    browser.post("/api/orders/suggestions", json={})
    answer = ask(staff_browser(browser), "what should I order and how much will it cost")
    assert numbers(answer)["Lines to order"] == 1
    assert "Total cost" not in numbers(answer) and "MAD" not in answer["sentence"]


def test_logged_out_people_cannot_ask(browser):
    set_up_shop(browser)
    browser.post("/api/auth/logout")
    assert browser.post("/api/ask", json={"question": "sales"}).status_code == 401


def test_each_shop_only_sees_its_own_data(browser, shop):
    other = create_other_shop()
    their_oil = new_part(other.organization_id, "Oil filter", "Filters")
    sell(other.organization_id, their_oil, "Other Shop", days_ago=0, quantity=100)

    assert numbers(ask(browser, "how many oil filters did we sell this week"))["Pieces sold"] == 5
    other_owner = logged_in_browser("owner@other.ma", OWNER_PASSWORD)
    assert numbers(ask(other_owner, "how many oil filters did we sell this week"))["Pieces sold"] == 100
    # Our branch names mean nothing in their shop.
    assert "branch" not in ask(other_owner, "sales this week in rabat")["filters"]


def test_asking_changes_nothing(browser, shop):
    def audit_count() -> int:
        with SessionLocal() as db:
            return db.scalar(select(func.count()).select_from(AuditLog))

    before = audit_count()
    ask(browser, "what should I order")
    ask(browser, "delete all old parts")
    assert audit_count() == before


def test_too_long_or_empty_questions_are_refused(browser, shop):
    assert browser.post("/api/ask", json={"question": ""}).status_code == 422
    assert browser.post("/api/ask", json={"question": "x" * 301}).status_code == 422


# The local model: optional, checked, and only asked when the rule is unsure

def test_ai_off_says_so_and_uses_the_rule(browser, shop):
    answer = ask(browser, "best sellers this week")
    assert answer["understood_by"] == "rule"
    assert answer["ai_note"].startswith("AI is off")


def test_model_is_not_asked_when_the_rule_is_sure(browser, shop, monkeypatch):
    monkeypatch.setattr(llm, "is_on", lambda: True)
    monkeypatch.setattr(llm, "ask_json", lambda *_: pytest.fail("the model should not be asked"))
    answer = ask(browser, "best sellers this week")
    assert answer["understood_by"] == "rule" and answer["ai_note"] is None


def test_model_reads_what_the_rule_is_unsure_about(browser, shop, monkeypatch):
    monkeypatch.setattr(llm, "is_on", lambda: True)
    monkeypatch.setattr(llm, "ask_json", lambda *_: {
        "type": "sales_of", "part": "oil filter", "category": None, "branch": RABAT, "period": "this_week",
    })
    answer = ask(browser, "chhal mcha mn filtre a huile f rbat")
    assert answer["understood_by"] == "model"
    assert answer["understood"] == f"Best guess. I understood: Sales of oil filter · {RABAT} · this week"
    assert numbers(answer)["Pieces sold"] == 2  # the number comes from the database, not the model
    # The other readings stay one tap away, without repeating the one chosen.
    assert [s["question_type"] for s in answer["suggestions"]] == ["stock_of_part", "forecast_of_part"]


def test_rule_readings_are_not_called_a_guess(browser, shop, monkeypatch):
    monkeypatch.setattr(llm, "is_on", lambda: True)
    answer = ask(browser, "oil filters sold this week")
    assert answer["understood"].startswith("I understood:") and answer["suggestions"] == []


@pytest.mark.parametrize("reply", [
    None,  # Ollama didn't answer
    {"type": "sales_of", "branch": "Paris", "pieces_sold": 9999},  # not allowed
    {"type": "cannot_answer", "part": None, "category": None, "branch": None, "period": None},
])
def test_no_usable_model_reading_means_not_sure(browser, shop, monkeypatch, reply):
    monkeypatch.setattr(llm, "is_on", lambda: True)
    monkeypatch.setattr(llm, "ask_json", lambda *_: reply)
    answer = ask(browser, "chhal mcha mn filtre a huile")
    assert answer["understood_by"] == "rule"
    assert answer["question_type"] == "not_sure" and answer["suggestions"]


def test_model_may_only_pick_one_of_the_offered_types(browser, shop, monkeypatch):
    monkeypatch.setattr(llm, "is_on", lambda: True)
    monkeypatch.setattr(llm, "ask_json", lambda *_: {
        "type": "late_deliveries", "part": None, "category": None, "branch": None, "period": None,
    })
    answer = ask(browser, "chhal mcha mn filtre a huile")
    assert "late_deliveries" not in [s["question_type"] for s in answer["suggestions"]]
    assert answer["question_type"] == "not_sure" and answer["understood_by"] == "rule"


def test_rule_only_reader_never_asks_the_model(browser, shop, monkeypatch):
    monkeypatch.setattr(llm, "is_on", lambda: True)
    monkeypatch.setattr(understand_module, "READER", "rule")
    monkeypatch.setattr(llm, "ask_json", lambda *_: pytest.fail("the model should not be asked"))
    assert ask(browser, "chhal mcha mn filtre a huile")["question_type"] == "not_sure"


def select_part(organization_id: uuid.UUID, name: str) -> uuid.UUID:
    with SessionLocal() as db:
        return db.scalar(select(Part.id).where(Part.organization_id == organization_id, Part.name == name))
