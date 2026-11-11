import uuid
from datetime import date, timedelta

import numpy as np
import pytest
from sqlalchemy import func, select

from app.alerts import sales_rules
from app.alerts.counts import chance_at_least, chance_at_most, spread
from app.alerts.problem import Problem, money, money_note
from app.alerts.run import DAILY_LIMIT, REPEAT_DAYS, SALES_DAILY_LIMIT, find_problems, pick_new, raise_alerts
from app.alerts.sales_rules import sales_problems
from app.alerts.shop_data import ShopData, load_shop_data
from app.alerts.stock_rules import stock_problems
from app.db import SessionLocal
from app.demo.demo_shop import create_demo_shop
from app.models import Alert, Branch, DemoPlantedProblem, Organization, Part, StockHistory, StockLevel
from app.stock_history import record_stock_history
from tests.helpers import add_member, audit_rows, create_other_shop, member_with_own_password, set_up_shop

DAYS = 140
FIRST_DAY = date(2026, 1, 1)
LAST = DAYS - 1


def shop_data(sold: list[np.ndarray], shelf: list[np.ndarray] | None = None, keys=None) -> ShopData:
    """Rows of daily sales (and stock), every part priced 100 MAD, cost 70 MAD."""
    rows = len(sold)
    sold = np.array(sold, dtype=float)
    return ShopData(
        keys=keys or [(uuid.uuid4(), uuid.uuid4()) for _ in range(rows)],
        first_day=FIRST_DAY,
        sold=sold,
        demand=sold.copy(),
        shelf=np.array(shelf, dtype=float) if shelf is not None else np.full(sold.shape, np.nan),
        price=np.full(rows, 10000),
        cost=np.full(rows, 7000),
        methods=["four_week_average"] * rows,
        currency="MAD",
    )


def steady(per_day: float, last_week: float | None = None) -> np.ndarray:
    days = np.full(DAYS, per_day)
    if last_week is not None:
        days[-7:] = last_week
    return days


# --- Sales spike / drop -------------------------------------------------------------------------


def test_a_week_far_above_the_usual_range_is_a_spike_with_its_real_numbers():
    [problem] = sales_problems(shop_data([steady(2, last_week=8)]), LAST)
    assert problem.kind == "sales_spike"
    assert problem.numbers["sold"] == 56 and problem.numbers["usual_low"] <= 14 <= problem.numbers["usual_high"] < 56
    assert problem.sentence.startswith(f"Sold 56 in the 7 days to 20 May, usually {problem.numbers['usual_low']} to")
    assert problem.money_at_stake == (56 - 14) * 10000  # pieces above the forecast x sale price
    assert problem.started_on == FIRST_DAY + timedelta(days=LAST - 6)


def test_a_week_far_below_the_usual_range_is_a_drop():
    [problem] = sales_problems(shop_data([steady(3, last_week=0)]), LAST)
    assert problem.kind == "sales_drop" and problem.numbers["sold"] == 0
    assert "MAD" not in problem.sentence  # money is kept apart, see money_note
    assert money_note(problem.kind, problem.money_at_stake, "MAD") == f"About {money(problem.money_at_stake, 'MAD')} of sales below usual."


def test_a_normal_week_raises_nothing():
    assert sales_problems(shop_data([steady(3)]), LAST) == []


def test_parts_that_sell_too_little_are_not_judged():
    assert sales_problems(shop_data([steady(0.5, last_week=4)]), LAST) == []  # 3.5 a week expected


def test_no_drop_while_the_shelf_was_empty():
    data = shop_data([steady(3, last_week=0)])
    data.demand[0, -3:] = np.nan  # empty shelf: low sales are explained, the stock rules handle it
    assert sales_problems(data, LAST) == []


def test_too_little_history_raises_nothing():
    assert sales_problems(shop_data([steady(2, last_week=8)]), 50) == []


def test_a_rare_week_is_not_a_spike_unless_it_is_up_by_half():
    assert sales_problems(shop_data([steady(20, last_week=28)]), LAST) == []  # +40%: blocked before rarity is even checked
    [problem] = sales_problems(shop_data([steady(20, last_week=40)]), LAST)  # +100%: clearly up by more than half, and rare
    assert problem.kind == "sales_spike"


def six_a_week(last_week: list[int]) -> np.ndarray:
    days = np.tile([1.0, 1, 1, 1, 1, 1, 0], DAYS // 7)
    days[-7:] = last_week
    return days


def test_a_change_needs_at_least_five_pieces(monkeypatch):
    monkeypatch.setattr(sales_rules, "PER_PART_BAR", 1.0)  # every week counts as rare here
    monkeypatch.setattr(sales_rules, "MIN_EXPECTED_WEEKLY", 1.0)
    assert sales_problems(shop_data([six_a_week([2, 2, 2, 1, 1, 1, 1])]), LAST) == []  # 10 sold: +67%, but only +4 pieces
    [problem] = sales_problems(shop_data([six_a_week([2, 2, 2, 2, 2, 1, 1])]), LAST)
    assert problem.numbers["sold"] == 12


def test_the_bar_does_not_depend_on_how_many_parts_are_checked():
    """Step 8c-1's bug: the bar used to be a shop-wide false-alarm budget split across every judged
    part, so a real spike could stop being caught just because more (unrelated, normal-selling)
    parts were judged that day — a bigger catalog meant a stricter bar, not more sales alerts.
    PER_PART_BAR is fixed now: checking many more ordinary parts alongside a real spike must not
    suppress it."""
    spiky = steady(2, last_week=8)  # 56 sold, 14 expected: very rare regardless of the bar chosen
    assert len(sales_problems(shop_data([spiky]), LAST)) == 1
    assert len(sales_problems(shop_data([spiky] + [steady(3)] * 500), LAST)) == 1


def uneven() -> np.ndarray:
    """Weeks (counted back from the last day) alternate 7 and 35 pieces: 21 a week on average."""
    weeks_back = (LAST - np.arange(DAYS)) // 7
    return np.where(weeks_back % 2 == 1, 1.0, 5.0)


def test_parts_that_usually_sell_unevenly_need_a_bigger_surprise():
    lumpy = uneven()
    lumpy[-7:] = 6  # 42 sold, 21 expected: ordinary for this part
    rows = [steady(3, last_week=6), lumpy] + [steady(3)] * 48
    [problem] = sales_problems(shop_data(rows), LAST)
    assert problem.numbers["sold"] == 42 and problem.numbers["expected"] == 21  # only the even seller


def test_count_model_tails():
    assert chance_at_most(0, 3.0, 0.0) == pytest.approx(np.exp(-3))  # Poisson
    assert chance_at_least(0, 3.0, 0.0) == 1.0
    assert chance_at_least(10, 3.0, 0.5) > chance_at_least(10, 3.0, 0.0)  # uneven sellers: fatter tails
    assert spread(np.full(10, 10.0), np.full(10, 10.0)) == 0.0
    assert spread(np.full(10, 10.0), np.array([0, 20] * 5, dtype=float)) == pytest.approx(0.9)


# --- Stock that doesn't match sales -------------------------------------------------------------


def changing_stock() -> np.ndarray:
    """A second part whose stock moves every day, so the shop is clearly sending stock numbers."""
    return np.arange(DAYS, 0, -1)


def test_negative_stock_is_raised_with_the_day_it_went_below_zero():
    shelf = np.full(DAYS, 5.0)
    shelf[-4:] = -2
    [problem] = stock_problems(shop_data([steady(0)], [shelf]), LAST)
    assert problem.kind == "negative_stock" and problem.numbers["quantity"] == -2
    assert problem.started_on == FIRST_DAY + timedelta(days=LAST - 3)
    assert problem.money_at_stake == 2 * 7000


def test_sales_on_days_that_started_and_ended_at_zero_are_raised():
    shelf = np.full(DAYS, 5.0)
    shelf[-4:] = 0
    sold = np.zeros(DAYS)
    sold[-2:] = [2, 1]
    [problem] = stock_problems(shop_data([sold], [shelf]), LAST)
    assert problem.kind == "sold_at_zero" and problem.numbers == {"sold": 3, "days": 2}
    assert problem.sentence.startswith("Sold 3 pieces on 2 days since")


def test_selling_the_last_piece_is_not_a_sale_at_zero():
    shelf = np.full(DAYS, 1.0)
    shelf[-1] = 0
    sold = np.zeros(DAYS)
    sold[-1] = 1
    assert stock_problems(shop_data([sold], [shelf]), LAST) == []


def test_stock_frozen_for_two_weeks_while_selling_is_raised():
    shelf = np.full(DAYS, 9.0)
    shelf[: LAST - 20] = 12
    [problem] = stock_problems(shop_data([steady(1), steady(0)], [shelf, changing_stock()]), LAST)
    assert problem.kind == "stock_frozen" and problem.numbers == {"quantity": 9, "sold": 20, "unchanged_days": 20}


def test_frozen_needs_fourteen_days_and_three_sold():
    shelf = np.full(DAYS, 9.0)
    shelf[: LAST - 10] = 12  # only 10 days unchanged
    assert stock_problems(shop_data([steady(1), steady(0)], [shelf, changing_stock()]), LAST) == []
    sold = np.zeros(DAYS)
    sold[-1] = 2  # unchanged a long time, but only 2 sold
    assert stock_problems(shop_data([sold, steady(0)], [np.full(DAYS, 9.0), changing_stock()]), LAST) == []


def test_frozen_is_not_judged_when_the_shop_sends_no_stock_numbers():
    assert stock_problems(shop_data([steady(1)], [np.full(DAYS, 9.0)]), LAST) == []


def test_one_stock_problem_per_part_the_clearest_first():
    shelf = np.full(DAYS, -1.0)
    [problem] = stock_problems(shop_data([steady(1), steady(0)], [shelf, changing_stock()]), LAST)
    assert problem.kind == "negative_stock"


def test_unknown_stock_raises_nothing():
    assert stock_problems(shop_data([steady(1)]), LAST) == []


# --- Ranking, daily limit, no repeat ------------------------------------------------------------


def problem(money: int, kind: str = "negative_stock") -> Problem:
    return Problem(uuid.uuid4(), uuid.uuid4(), kind, FIRST_DAY, money, f"worth {money}", {})


def test_new_alerts_are_ranked_by_money_at_stake_and_capped():
    problems = [problem(m) for m in (5, 50, 20, 40)]
    assert [p.money_at_stake for p in pick_new(problems, set(), 3, 3)] == [50, 40, 20]
    assert pick_new(problems, set(), 0, 3) == []


def test_blocked_problems_are_skipped():
    problems = [problem(10), problem(20)]
    assert pick_new(problems, {problems[1].key}, 10, 3) == [problems[0]]


def test_at_most_three_sales_alerts_a_day_so_stock_problems_still_get_through():
    sales = [problem(m, "sales_spike") for m in (900, 800, 700, 600, 500)]
    stock = [problem(m) for m in (20, 10)]
    picked = pick_new(sales + stock, set(), DAILY_LIMIT, SALES_DAILY_LIMIT)
    assert [p.money_at_stake for p in picked] == [900, 800, 700, 20, 10]
    assert [p.group for p in picked] == ["worth_a_look"] * 3 + ["needs_action"] * 2
    assert len(pick_new(sales, set(), DAILY_LIMIT, 1)) == 1  # 2 already raised today: 1 left


def make_shop_with_parts(count: int) -> tuple[uuid.UUID, list[tuple[uuid.UUID, uuid.UUID]]]:
    with SessionLocal() as db:
        shop = Organization(name="Alert Shop")
        db.add(shop)
        db.flush()
        branch = Branch(organization_id=shop.id, name="Main")
        parts = [Part(organization_id=shop.id, sku=f"P{i}", name=f"Part {i}", unit_cost=7000, sale_price=10000) for i in range(count)]
        db.add_all([branch, *parts])
        db.commit()
        return shop.id, [(p.id, branch.id) for p in parts]


def negative_shop_data(keys, worth: list[int]) -> ShopData:
    """One negative stock problem per part; part i is -worth[i] pieces."""
    shelves = [np.full(DAYS, -float(w)) for w in worth]
    return shop_data([steady(1)] * len(keys), shelves, keys)


def test_at_most_ten_new_alerts_a_day_most_money_first():
    shop_id, keys = make_shop_with_parts(15)
    data = negative_shop_data(keys, list(range(1, 16)))
    today = FIRST_DAY + timedelta(days=LAST)
    with SessionLocal() as db:
        first = raise_alerts(db, shop_id, data, today)
        again = raise_alerts(db, shop_id, data, today)  # e.g. after an import, the same day
        next_day = raise_alerts(db, shop_id, data, today + timedelta(days=1))
        db.commit()
    assert len(first) == DAILY_LIMIT and again == []
    assert [a.numbers["quantity"] for a in first] == list(range(-15, -5))
    assert sorted(a.numbers["quantity"] for a in next_day) == list(range(-5, 0))  # the rest, one day later


def test_the_same_problem_is_not_raised_again_every_day():
    shop_id, keys = make_shop_with_parts(1)
    data = negative_shop_data(keys, [3])
    today = FIRST_DAY + timedelta(days=LAST)
    with SessionLocal() as db:
        [alert] = raise_alerts(db, shop_id, data, today)
        assert raise_alerts(db, shop_id, data, today + timedelta(days=1)) == []  # still open
        alert.status = "not_a_problem"
        assert raise_alerts(db, shop_id, data, today + timedelta(days=REPEAT_DAYS - 1)) == []  # reviewed, but recent
        assert len(raise_alerts(db, shop_id, data, today + timedelta(days=REPEAT_DAYS))) == 1  # still wrong a month later
        db.commit()


def test_alerts_judge_the_week_that_ends_on_the_last_imported_sales_day():
    sold = steady(2, last_week=8)
    sold = np.concatenate([sold, np.zeros(5)])  # 5 days with no sales imported yet
    data = shop_data([sold])
    [found] = find_problems(data, FIRST_DAY + timedelta(days=DAYS + 4))
    assert found.kind == "sales_spike" and found.numbers["week_end"] == (FIRST_DAY + timedelta(days=LAST)).isoformat()


# --- Stock history and the demo -----------------------------------------------------------------


def test_stock_history_saves_only_changes_and_keeps_the_end_of_day_number():
    shop_id, [(part_id, branch_id)] = make_shop_with_parts(1)
    day = date(2026, 3, 1)
    with SessionLocal() as db:
        db.add(StockLevel(organization_id=shop_id, part_id=part_id, branch_id=branch_id, quantity=5))
        db.flush()
        assert record_stock_history(db, shop_id, day) == 1
        assert record_stock_history(db, shop_id, day) == 0
        db.scalar(select(StockLevel)).quantity = 4
        db.flush()
        assert record_stock_history(db, shop_id, day) == 1  # same day: updated, not added
        assert record_stock_history(db, shop_id, day + timedelta(days=1)) == 0
        db.scalar(select(StockLevel)).quantity = 3
        db.flush()
        record_stock_history(db, shop_id, day + timedelta(days=2))
        db.commit()
        rows = db.execute(select(StockHistory.day, StockHistory.quantity).order_by(StockHistory.day)).all()
    assert rows == [(day, 4), (day + timedelta(days=2), 3)]


def test_the_demo_planted_negative_stock_is_found():
    last_day = date(2026, 6, 30)
    with SessionLocal() as db:
        shop, _ = create_demo_shop(db, last_day, parts_count=40, history_days=200)
        db.flush()
        found = find_problems(load_shop_data(db, shop.id, last_day), last_day)
        planted = db.scalars(select(DemoPlantedProblem.part_id).where(DemoPlantedProblem.kind == "negative_stock")).all()
        db.rollback()
    assert planted and all(any(f.kind == "negative_stock" and f.part_id == part_id for f in found) for part_id in planted)
    assert all(f.money_at_stake >= 0 and any(ch.isdigit() for ch in f.sentence) for f in found)


# --- Endpoints ----------------------------------------------------------------------------------


def alert_in_shop(organization_id: uuid.UUID) -> uuid.UUID:
    with SessionLocal() as db:
        branch = db.scalar(select(Branch).where(Branch.organization_id == organization_id))
        part = Part(organization_id=organization_id, sku="BP-1", name="Brake pads", unit_cost=7000)
        db.add(part)
        db.flush()
        alert = Alert(
            organization_id=organization_id, part_id=part.id, branch_id=branch.id, kind="negative_stock",
            sentence="Stock shows -2 since 1 Mar.", numbers={"quantity": -2}, money_at_stake=14000,
            started_on=date(2026, 3, 1), raised_on=date(2026, 3, 2), status="open",
        )
        db.add(alert)
        db.commit()
        return alert.id


def test_everyone_sees_alerts_but_only_owners_and_managers_review_them(browser):
    set_up_shop(browser)
    alert_id = alert_in_shop(_shop_id())
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")

    [listed] = staff.get("/api/alerts", params={"status": "open"}).json()
    assert listed["sentence"] == "Stock shows -2 since 1 Mar." and listed["part_name"] == "Brake pads"
    assert listed["group"] == "needs_action"
    assert "money_at_stake" not in listed  # staff: no money field at all, not even zero
    assert len(staff.get("/api/alerts", params={"group": "needs_action"}).json()) == 1
    assert staff.get("/api/alerts", params={"group": "worth_a_look"}).json() == []
    assert staff.post(f"/api/alerts/{alert_id}/review", json={"status": "looked_at"}).status_code == 403

    reviewed = browser.post(f"/api/alerts/{alert_id}/review", json={"status": "not_a_problem"})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "not_a_problem" and reviewed.json()["reviewed_at"]
    assert reviewed.json()["reviewed_by_name"] == "Sara Owner"
    assert browser.get("/api/alerts").json()[0]["reviewed_by_name"] == "Sara Owner"
    [row] = audit_rows("alert.reviewed")
    assert row.before == {"status": "open"} and row.after["status"] == "not_a_problem" and row.user_id is not None
    assert browser.get("/api/alerts", params={"status": "open"}).json() == []


def test_owners_and_managers_see_money_staff_never_does(browser):
    """The raw JSON itself, not just the browser's display: no money key, no money in the sentence."""
    set_up_shop(browser)
    alert_in_shop(_shop_id())
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")

    [owner_alert] = browser.get("/api/alerts").json()
    assert owner_alert["money_at_stake"] == 14000
    assert owner_alert["sentence"] == "Stock shows -2 since 1 Mar. About 140 MAD of stock to recount."

    [staff_alert] = staff.get("/api/alerts").json()
    assert "money_at_stake" not in staff_alert
    assert staff_alert["sentence"] == "Stock shows -2 since 1 Mar."
    assert "MAD" not in staff_alert["sentence"] and "140" not in staff_alert["sentence"]


def test_alerts_of_another_shop_cannot_be_reviewed(browser):
    set_up_shop(browser)
    other = create_other_shop()
    alert_id = alert_in_shop(other.organization_id)
    assert browser.post(f"/api/alerts/{alert_id}/review", json={"status": "looked_at"}).status_code == 404
    assert browser.get("/api/alerts").json() == []
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Alert).where(Alert.status == "open")) == 1


def _shop_id() -> uuid.UUID:
    with SessionLocal() as db:
        return db.scalar(select(Organization.id).where(~Organization.is_demo))
