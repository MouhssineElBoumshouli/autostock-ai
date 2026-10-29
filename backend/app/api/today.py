"""The Today page: everything an owner needs to glance at each morning, in one call.

Needs action and worth a look reuse the alerts engine's own grouping (app/alerts/problem.py).
To order reads the pending lines of the latest order run. Late deliveries are purchase orders
sent longer ago than their supplier's delivery time and not yet fully received. This week's
sales are measured against a simple baseline: the average of the 4 weeks before it. Owners also
see when the backups stopped (none good for 2 days, app/backups.py).
"""

import uuid
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.alerts.problem import NEEDS_ACTION, SALES_KINDS, WORTH_A_LOOK, money_note
from app.auth.permissions import require_role
from app.backups import backup_folder, backup_status, is_overdue
from app.config import BACKUP_DIR
from app.db import get_session, utc_now
from app.models import Alert, Branch, OrderRun, OrderSuggestion, Organization, Part, PurchaseOrder, SaleLine, Supplier, User
from app.shop_day import shop_today

router = APIRouter(prefix="/api/today")
anyone = require_role()

SHOWN_ALERTS = 5
WEEKS_SHOWN = 12
BASELINE_WEEKS = 4
TOP_PARTS_SHOWN = 5
PENDING_STATUSES = ("suggested", "cut_by_budget")


class AlertSummary(BaseModel):
    """What staff see: no money. `sentence` is English; the website builds it in the person's
    language from `kind`, `numbers` and `started_on`."""

    id: uuid.UUID
    kind: str
    sentence: str
    numbers: dict
    started_on: date
    part_name: str
    branch_name: str
    raised_on: date


class AlertSummaryWithMoney(AlertSummary):
    money_at_stake: int


class ToOrderLines(BaseModel):
    """What staff see: how many lines, no money."""

    lines: int


class ToOrderSummary(ToOrderLines):
    """What owners and managers also see."""

    total_cost: int


class LateDelivery(BaseModel):
    id: uuid.UUID
    order_number: str
    supplier_name: str
    sent_at: datetime
    days_late: int


class WeekPoint(BaseModel):
    week_start: date
    quantity: int


class TopPart(BaseModel):
    part_id: uuid.UUID
    sku: str
    name: str
    quantity: int


class WeeklySales(BaseModel):
    this_week: int
    normal: int  # average of the BASELINE_WEEKS weeks before this one
    weeks: list[WeekPoint]
    top_parts: list[TopPart]


class BackupOverdue(BaseModel):
    """Owners only: the last good backup is older than 2 days, or there is none yet."""

    last_good_at: datetime | None


class TodayOut(BaseModel):
    needs_action: list[AlertSummaryWithMoney | AlertSummary]
    needs_action_total: int
    worth_a_look: list[AlertSummaryWithMoney | AlertSummary]
    worth_a_look_total: int
    to_order: ToOrderSummary | ToOrderLines | None
    late_deliveries: list[LateDelivery]
    weekly_sales: WeeklySales | None
    backup_overdue: BackupOverdue | None = None  # owners only


Group = Literal["needs_action", "worth_a_look"]


@router.get("")
def today(user: User = Depends(anyone), db: Session = Depends(get_session)) -> TodayOut:
    can_see_money = user.role != "staff"
    currency = db.scalar(select(Organization.currency).where(Organization.id == user.organization_id)) if can_see_money else None
    needs_action, needs_action_total = open_alert_group(db, user.organization_id, NEEDS_ACTION, currency)
    worth_a_look, worth_a_look_total = open_alert_group(db, user.organization_id, WORTH_A_LOOK, currency)
    return TodayOut(
        needs_action=needs_action,
        needs_action_total=needs_action_total,
        worth_a_look=worth_a_look,
        worth_a_look_total=worth_a_look_total,
        to_order=to_order_summary(db, user.organization_id, can_see_money),
        late_deliveries=find_late_deliveries(db, user.organization_id, shop_today()),
        weekly_sales=weekly_sales(db, user.organization_id),
        backup_overdue=backup_overdue(user),
    )


def backup_overdue(user: User) -> BackupOverdue | None:
    if user.role != "owner" or not BACKUP_DIR:
        return None
    status = backup_status(backup_folder())
    return BackupOverdue(last_good_at=status.last_good_at) if is_overdue(status, utc_now()) else None


def open_alert_group(db: Session, organization_id: uuid.UUID, group: Group, currency: str | None) -> tuple[list[AlertSummary], int]:
    filters = [Alert.organization_id == organization_id, Alert.status == "open"]
    filters.append(Alert.kind.in_(SALES_KINDS) if group == WORTH_A_LOOK else Alert.kind.not_in(SALES_KINDS))
    total = db.scalar(select(func.count()).select_from(Alert).where(*filters)) or 0
    rows = db.execute(
        select(Alert, Part.name, Branch.name)
        .join(Part, Part.id == Alert.part_id)
        .join(Branch, Branch.id == Alert.branch_id)
        .where(*filters)
        .order_by(Alert.money_at_stake.desc(), Alert.raised_on.desc())
        .limit(SHOWN_ALERTS)
    ).all()
    return [_summary(alert, part_name, branch_name, currency) for alert, part_name, branch_name in rows], total


def _summary(alert: Alert, part_name: str, branch_name: str, currency: str | None) -> AlertSummary:
    fields = dict(
        id=alert.id, kind=alert.kind, numbers=alert.numbers, started_on=alert.started_on, part_name=part_name,
        branch_name=branch_name, raised_on=alert.raised_on,
    )
    if currency is None:
        return AlertSummary(**fields, sentence=alert.sentence)
    return AlertSummaryWithMoney(
        **fields, sentence=f"{alert.sentence} {money_note(alert.kind, alert.money_at_stake, currency)}",
        money_at_stake=alert.money_at_stake,
    )


def to_order_summary(db: Session, organization_id: uuid.UUID, can_see_money: bool) -> ToOrderSummary | ToOrderLines | None:
    run = db.scalar(
        select(OrderRun).where(OrderRun.organization_id == organization_id).order_by(OrderRun.created_at.desc()).limit(1)
    )
    if run is None:
        return None
    lines, cost = db.execute(
        select(func.count(), func.coalesce(func.sum(OrderSuggestion.line_cost), 0)).where(
            OrderSuggestion.organization_id == organization_id,
            OrderSuggestion.run_id == run.id,
            OrderSuggestion.status.in_(PENDING_STATUSES),
        )
    ).one()
    return ToOrderSummary(lines=lines, total_cost=cost) if can_see_money else ToOrderLines(lines=lines)


def find_late_deliveries(db: Session, organization_id: uuid.UUID, today: date) -> list[LateDelivery]:
    rows = db.execute(
        select(PurchaseOrder, Supplier.name, Supplier.delivery_days)
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .where(
            PurchaseOrder.organization_id == organization_id,
            PurchaseOrder.status == "sent",
            Supplier.delivery_days.is_not(None),
        )
        .order_by(PurchaseOrder.sent_at)
    )
    late = []
    for po, supplier_name, delivery_days in rows:
        days_since = (today - po.sent_at.date()).days
        if days_since > delivery_days:
            late.append(
                LateDelivery(
                    id=po.id, order_number=po.order_number, supplier_name=supplier_name,
                    sent_at=po.sent_at, days_late=days_since - delivery_days,
                )
            )
    return late


def weekly_sales(db: Session, organization_id: uuid.UUID) -> WeeklySales | None:
    last_day = db.scalar(select(func.max(SaleLine.sold_on)).where(SaleLine.organization_id == organization_id))
    if last_day is None:
        return None

    first_day = last_day - timedelta(days=WEEKS_SHOWN * 7 - 1)
    daily = dict(
        db.execute(
            select(SaleLine.sold_on, func.sum(SaleLine.quantity))
            .where(SaleLine.organization_id == organization_id, SaleLine.sold_on >= first_day, SaleLine.sold_on <= last_day)
            .group_by(SaleLine.sold_on)
        ).all()
    )
    weeks = [
        WeekPoint(
            week_start=first_day + timedelta(days=7 * week),
            quantity=sum(daily.get(first_day + timedelta(days=7 * week + day), 0) for day in range(7)),
        )
        for week in range(WEEKS_SHOWN)
    ]
    this_week = weeks[-1].quantity
    previous = weeks[-1 - BASELINE_WEEKS : -1]
    normal = round(sum(week.quantity for week in previous) / len(previous))

    this_week_start = weeks[-1].week_start
    top_rows = db.execute(
        select(SaleLine.part_id, Part.sku, Part.name, func.sum(SaleLine.quantity).label("quantity"))
        .join(Part, Part.id == SaleLine.part_id)
        .where(SaleLine.organization_id == organization_id, SaleLine.sold_on >= this_week_start, SaleLine.sold_on <= last_day)
        .group_by(SaleLine.part_id, Part.sku, Part.name)
        .order_by(func.sum(SaleLine.quantity).desc())
        .limit(TOP_PARTS_SHOWN)
    )
    top_parts = [TopPart(part_id=part_id, sku=sku, name=name, quantity=int(quantity)) for part_id, sku, name, quantity in top_rows]

    return WeeklySales(this_week=this_week, normal=normal, weeks=weeks, top_parts=top_parts)
