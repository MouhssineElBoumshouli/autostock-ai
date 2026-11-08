"""A supplier's delivery time, without anyone having to type it.

Where the number comes from, from least to most trusted:
  estimated  nothing known yet: DEFAULT_DELIVERY_DAYS is used, and said so
  file       the parts import had a delivery-time column (app/imports/parts_import.py)
  learned    the typical (median) days its recent received orders took
  owner      typed in Settings: kept as it is until the owner empties it again

Real deliveries replace a file's number once there are DELIVERIES_TO_REPLACE_FILE of them; before
that, one odd delivery would wipe out what the shop wrote. With nothing known, the first delivery
is already better than a guess.
"""

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_change
from app.models import PurchaseOrder, Supplier, User
from app.shop_day import shop_today

DEFAULT_DELIVERY_DAYS = 7
RECENT_DELIVERIES = 5
DELIVERIES_TO_REPLACE_FILE = 3

Source = Literal["estimated", "file", "learned", "owner"]


@dataclass(frozen=True)
class DeliveryTime:
    days: int
    source: Source
    learned_from: int = 0  # deliveries behind a "learned" value


def delivery_time(supplier: Supplier | None) -> DeliveryTime:
    """The delivery time "what to order" uses for this supplier, and where it came from."""
    if supplier is None or supplier.delivery_days is None:
        return DeliveryTime(DEFAULT_DELIVERY_DAYS, "estimated")
    return DeliveryTime(supplier.delivery_days, supplier.delivery_source or "owner", supplier.delivery_learned_from)


def days_taken(sent_at: datetime, received_at: datetime) -> int:
    """Days from sent to received on the shop's calendar. Same day counts as 1."""
    return max(1, (shop_today(received_at) - shop_today(sent_at)).days)


def file_may_set(supplier: Supplier) -> bool:
    """A file fills in an unknown delivery time or replaces an earlier file's, but never the owner's
    choice nor one learned from enough real deliveries."""
    if supplier.delivery_days is None or supplier.delivery_source == "file":
        return True
    return supplier.delivery_source == "learned" and supplier.delivery_learned_from < DELIVERIES_TO_REPLACE_FILE


def set_from_file(db: Session, user: User, supplier: Supplier, days: int) -> None:
    _change(db, user, supplier, days, "file", 0)


@dataclass(frozen=True)
class RecentDeliveries:
    days: int  # the typical (middle) value
    count: int  # how many deliveries it comes from


def recent_deliveries(db: Session, supplier: Supplier) -> RecentDeliveries | None:
    """What the supplier's last RECENT_DELIVERIES received orders say, or None before any."""
    recent = db.scalars(
        select(PurchaseOrder.days_taken)
        .where(PurchaseOrder.organization_id == supplier.organization_id, PurchaseOrder.supplier_id == supplier.id,
               PurchaseOrder.days_taken.is_not(None))
        .order_by(PurchaseOrder.received_at.desc())
        .limit(RECENT_DELIVERIES)
    ).all()
    # The higher middle value when there are two: always a real delivery, and running short is worse.
    return RecentDeliveries(statistics.median_high(recent), len(recent)) if recent else None


def deliveries_disagree(db: Session, supplier: Supplier) -> RecentDeliveries | None:
    """For a delivery time the owner typed: what enough real deliveries say instead, when it differs.
    Shown next to it in Settings; nothing changes until the owner clicks."""
    if supplier.delivery_source != "owner" or supplier.delivery_days is None:
        return None
    recent = recent_deliveries(db, supplier)
    if recent is None or recent.count < DELIVERIES_TO_REPLACE_FILE or recent.days == supplier.delivery_days:
        return None
    return recent


def learn_from_deliveries(db: Session, user: User, supplier: Supplier) -> None:
    """After an order is received: follow the typical days of the supplier's recent deliveries."""
    if supplier.delivery_source == "owner" and supplier.delivery_days is not None:
        return
    recent = recent_deliveries(db, supplier)
    if recent is None:
        return
    if supplier.delivery_source == "file" and recent.count < DELIVERIES_TO_REPLACE_FILE:
        return
    _change(db, user, supplier, recent.days, "learned", recent.count)


def set_by_owner(db: Session, user: User, supplier: Supplier, days: int | None) -> None:
    """The owner typed a number (it stays), or emptied the field: back to automatic."""
    if days == supplier.delivery_days:
        return
    if days is not None:
        _change(db, user, supplier, days, "owner", 0)
        return
    _change(db, user, supplier, None, None, 0)
    learn_from_deliveries(db, user, supplier)


def _change(db: Session, user: User, supplier: Supplier, days: int | None, source: str | None, learned_from: int) -> None:
    before = _snapshot(supplier)
    supplier.delivery_days, supplier.delivery_source, supplier.delivery_learned_from = days, source, learned_from
    after = _snapshot(supplier)
    if after != before:
        record_change(db, user, "supplier.delivery_time_changed", "supplier", supplier.id,
                      before={"name": supplier.name, **before}, after={"name": supplier.name, **after})


def _snapshot(supplier: Supplier) -> dict:
    return {"delivery_days": supplier.delivery_days, "source": supplier.delivery_source,
            "learned_from": supplier.delivery_learned_from}
