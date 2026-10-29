"""The shop's day. The server may run in UTC; the shop lives in its own time zone (TZ, default
Africa/Casablanca), so at 00:30 in Casablanca it is already the next day for the shop."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.config import SHOP_TIMEZONE


def shop_today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(ZoneInfo(SHOP_TIMEZONE)).date()
