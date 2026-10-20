"""Periods as day ranges. "Today" is the shop's last day with sales (like the Today page), so a
shop that imports its sales weekly still gets sensible answers. Weeks are the 7 days ending then."""

from datetime import date, timedelta

DayRange = tuple[date, date]
DEFAULT_PERIOD = "last_30_days"
LABELS = {
    "today": "today", "yesterday": "yesterday", "this_week": "this week", "last_week": "last week",
    "this_month": "this month", "last_month": "last month", "this_year": "this year", "last_30_days": "the last 30 days",
}


def day_range(period: str, today: date) -> DayRange:
    if period == "today":
        return today, today
    if period == "yesterday":
        return today - timedelta(days=1), today - timedelta(days=1)
    if period == "this_week":
        return today - timedelta(days=6), today
    if period == "last_week":
        return today - timedelta(days=13), today - timedelta(days=7)
    if period == "this_month":
        return today.replace(day=1), today
    if period == "last_month":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if period == "this_year":
        return today.replace(month=1, day=1), today
    return today - timedelta(days=29), today


def range_before(period: str, today: date) -> DayRange:
    """The period just before, cut to the same number of days so the comparison is fair
    (1-20 October is compared with 1-20 September, not with all of September). A whole past
    month is compared with the whole month before it."""
    if period in ("today", "yesterday", "this_week", "last_week", "last_30_days"):
        first, last = day_range(period, today)
        length = (last - first).days + 1
        return first - timedelta(days=length), last - timedelta(days=length)
    first, last = day_range(period, today)
    if period == "last_month":
        end = first - timedelta(days=1)
        return end.replace(day=1), end
    if period == "this_year":
        return _same_day_year_before(first), _same_day_year_before(last)
    previous_first = (first - timedelta(days=1)).replace(day=1)
    previous_last = min(previous_first + (last - first), first - timedelta(days=1))
    return previous_first, previous_last


def _same_day_year_before(day: date) -> date:
    return day.replace(year=day.year - 1, day=28) if (day.month, day.day) == (2, 29) else day.replace(year=day.year - 1)
