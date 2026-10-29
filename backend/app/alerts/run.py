"""Turns the day's problems into alerts, without flooding the shop:
- at most DAILY_LIMIT new alerts per shop per day, the most money at stake first, and of those at
  most SALES_DAILY_LIMIT "Worth a look" sales changes, so they never crowd out "Needs action";
- the same problem (same part, branch and kind) is not raised again while its alert is open, nor
  for REPEAT_DAYS after it was raised.
Runs every day and after each sales or stock import.
"""

import asyncio
import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.alerts.problem import WORTH_A_LOOK, Problem, group_of
from app.alerts.sales_rules import sales_problems
from app.alerts.shop_data import ShopData, load_shop_data
from app.alerts.stock_rules import stock_problems
from app.db import SessionLocal
from app.models import Alert, Organization
from app.shop_day import shop_today

log = logging.getLogger(__name__)
DAILY_LIMIT = 10
SALES_DAILY_LIMIT = 3
REPEAT_DAYS = 30
CHECK_EVERY_SECONDS = 3600


def find_problems(data: ShopData, today: date) -> list[Problem]:
    """Everything unusual in the week that ends on the last day with imported sales."""
    end = data.last_sales_index((today - data.first_day).days)
    if end is None:
        return []
    return sales_problems(data, end) + stock_problems(data, end)


def pick_new(problems: list[Problem], blocked: set[tuple], room: int, sales_room: int) -> list[Problem]:
    """The problems to raise: not blocked by the no-repeat rule, most money at stake first, with at
    most `sales_room` sales changes among them."""
    fresh = sorted((p for p in problems if p.key not in blocked), key=lambda p: (-p.money_at_stake, p.sentence))
    picked = []
    for p in fresh:
        if len(picked) >= room:
            break
        if p.group == WORTH_A_LOOK:
            if sales_room <= 0:
                continue
            sales_room -= 1
        picked.append(p)
    return picked


def raise_alerts(db: Session, organization_id: uuid.UUID, data: ShopData, today: date) -> list[Alert]:
    """Saves today's new alerts. The caller commits."""
    blocked = set(
        db.execute(
            select(Alert.part_id, Alert.branch_id, Alert.kind).where(
                Alert.organization_id == organization_id,
                or_(Alert.status == "open", Alert.raised_on > today - timedelta(days=REPEAT_DAYS)),
            )
        ).all()
    )
    today_kinds = db.scalars(select(Alert.kind).where(Alert.organization_id == organization_id, Alert.raised_on == today)).all()
    sales_today = sum(1 for kind in today_kinds if group_of(kind) == WORTH_A_LOOK)
    found = find_problems(data, today)
    alerts = [
        Alert(
            organization_id=organization_id,
            part_id=p.part_id,
            branch_id=p.branch_id,
            kind=p.kind,
            sentence=p.sentence,
            numbers=p.numbers,
            money_at_stake=p.money_at_stake,
            started_on=p.started_on,
            raised_on=today,
            status="open",
        )
        for p in pick_new(found, blocked, DAILY_LIMIT - len(today_kinds), SALES_DAILY_LIMIT - sales_today)
    ]
    db.add_all(alerts)
    db.flush()
    return alerts


def run_alerts(db: Session, organization_id: uuid.UUID, today: date) -> list[Alert]:
    data = load_shop_data(db, organization_id, today)
    return raise_alerts(db, organization_id, data, today) if data else []


def run_alerts_now(organization_id: uuid.UUID) -> None:
    """For one shop, in its own session (used after an import)."""
    with SessionLocal() as db:
        try:
            run_alerts(db, organization_id, shop_today())
            db.commit()
        except Exception:
            log.exception("Alerts failed for %s", organization_id)


async def keep_raising_alerts() -> None:
    """Runs while the server is up: once a day per shop, checked hourly so a restart never skips a day.
    Real shops only: the demo shop's alerts come from its replay (app/demo/check_alerts.py)."""
    checked_on: dict[uuid.UUID, date] = {}
    while True:
        today = shop_today()
        try:
            with SessionLocal() as db:
                shops = db.scalars(select(Organization.id).where(~Organization.is_demo)).all()
            for shop_id in shops:
                if checked_on.get(shop_id) != today:
                    await asyncio.to_thread(run_alerts_now, shop_id)
                    checked_on[shop_id] = today
        except Exception:
            log.exception("Daily alerts failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
