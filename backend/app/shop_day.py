"""The shop's day and clock. The server may run in UTC; the shop lives in its own time zone (TZ,
default Africa/Casablanca), so at 00:30 in Casablanca it is already the next day for the shop.

Morocco moved to permanent UTC+0 on 20 Sep 2026 (no more summer time), but a browser or a shop PC
keeps whatever time zone data it shipped with until it is updated, so an old one still shows an
hour ahead. The website never computes this itself (app/shop_day.py, not frontend/src/lib/format.ts):
it asks the server for today's offset (GET /api/today/shop-time) and shifts by that, trusting this
container's own, up-to-date tzdata package instead of whichever computer happens to be looking."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.config import SHOP_TIMEZONE

ZONE = ZoneInfo(SHOP_TIMEZONE)


def shop_today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(ZONE).date()


def shop_utc_offset_minutes(now: datetime | None = None) -> int:
    """Minutes to add to a UTC moment to get the shop's own clock, right now (it can change across
    a daylight-saving boundary elsewhere, which is why this is asked for, not hardcoded)."""
    offset = (now or datetime.now(UTC)).astimezone(ZONE).utcoffset()
    return int(offset.total_seconds() // 60) if offset else 0


def to_shop_time(moment: datetime | None) -> datetime | None:
    """A timezone-aware moment -> the shop's own wall-clock time, with no time zone attached
    (Excel, like most spreadsheets, can't store one): used when writing dates into the data export."""
    return None if moment is None else moment.astimezone(ZONE).replace(tzinfo=None)
