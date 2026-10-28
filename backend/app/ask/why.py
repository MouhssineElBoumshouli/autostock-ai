"""Why a part's sales changed, worked out by rules from the shop's own data. No model guesses it.

The reasons looked at, in this order (the first one found is the main reason):
1. days out of stock: at least STOCK_OUT_DAYS more days with zero stock than before (or fewer, for a rise);
2. price: the average selling price moved by at least PRICE_PERCENT;
3. the season: sales are close to the same days last year, so the change is normal for this time of year;
4. an open alert on the part that points the same way (a drop, stock not moving, a spike...).
A change of only a few pieces is "about the same"; one under SMALL_CHANGE_PERCENT is called small.
When none of the reasons fits, the answer says so honestly instead of guessing.
"""

from dataclasses import dataclass

SMALL_CHANGE_PERCENT = 10
SMALL_CHANGE_PIECES = 3
STOCK_OUT_DAYS = 3
PRICE_PERCENT = 5
SEASON_PERCENT = 15
ALERTS_FOR = {"down": ("sales_drop", "stock_frozen", "negative_stock", "sold_at_zero"), "up": ("sales_spike",)}


@dataclass(frozen=True)
class SalesFacts:
    now: int
    before: int
    last_year: int
    out_now: int  # days with zero stock this period, one per branch (and per part) that was out
    out_before: int
    price_now: int | None  # average selling price in centimes, None without priced sales
    price_before: int | None
    alerts: tuple[dict, ...] = ()  # open alerts on the part: {"kind", "branch", ...}


def direction(now: int, before: int) -> str:
    """"up", "down" or "same" (a change of only a few pieces). A small change in percent still has a
    direction: the person asked why, so the reasons that fit are given, and the answer says it is small."""
    change = now - before
    if abs(change) < SMALL_CHANGE_PIECES:
        return "same"
    return "up" if change > 0 else "down"


def reasons(facts: SalesFacts) -> list[dict]:
    """The reasons that fit, the main one first. Empty when no rule explains the change."""
    way = direction(facts.now, facts.before)
    if way == "same":
        return []
    found = []
    more_days_out = facts.out_now - facts.out_before
    if (way == "down" and more_days_out >= STOCK_OUT_DAYS) or (way == "up" and -more_days_out >= STOCK_OUT_DAYS):
        found.append({"kind": "out_of_stock" if way == "down" else "back_in_stock",
                      "days_now": facts.out_now, "days_before": facts.out_before})
    if facts.price_now and facts.price_before:
        price_change = round(100 * (facts.price_now - facts.price_before) / facts.price_before)
        if (way == "down" and price_change >= PRICE_PERCENT) or (way == "up" and price_change <= -PRICE_PERCENT):
            found.append({"kind": "price_up" if price_change > 0 else "price_down", "percent": abs(price_change),
                          "price_now": facts.price_now, "price_before": facts.price_before})
    if facts.last_year and abs(facts.now - facts.last_year) * 100 <= SEASON_PERCENT * facts.last_year:
        found.append({"kind": "season", "last_year": facts.last_year})
    alert = next((alert for alert in facts.alerts if alert["kind"] in ALERTS_FOR[way]), None)
    if alert:
        found.append({"kind": "alert", "alert_kind": alert["kind"], "branch": alert["branch"]})
    return found
