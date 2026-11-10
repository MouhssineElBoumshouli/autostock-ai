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
    # How many distinct parts and branches out_now/out_before are a sum over, so the sentence can
    # say "in total, across 5 parts and 3 branches" instead of reading like one part's own number.
    out_now_parts: int = 0
    out_now_branches: int = 0
    out_before_parts: int = 0
    out_before_branches: int = 0


def direction(now: int, before: int) -> str:
    """"up", "down" or "same" (a change of only a few pieces). A small change in percent still has a
    direction: the person asked why, so the reasons that fit are given, and the answer says it is small."""
    change = now - before
    if abs(change) < SMALL_CHANGE_PIECES:
        return "same"
    return "up" if change > 0 else "down"


def last_year_compared(now: int, last_year: int) -> str | None:
    """How the same days last year compare with now: "higher", "lower" or "same"; None without sales then."""
    if not last_year:
        return None
    if abs(now - last_year) * 100 <= SEASON_PERCENT * last_year:
        return "same"
    return "higher" if last_year > now else "lower"


MAIN_REASON = {
    "out_of_stock": "the part was out of stock on more days this period than before",
    "back_in_stock": "the part is back in stock: it was out of stock on fewer days this period than before",
    "price_up": "the average selling price went up",
    "price_down": "the average selling price went down",
    "season": "normal for the season: the same days last year sold about as many",
    "alert": "an open alert points the same way",
}
LAST_YEAR = {
    "higher": "the same days last year sold MORE than this period, so the season does not explain it",
    "lower": "the same days last year sold FEWER than this period, so the season does not explain it",
    "same": "the same days last year sold about as many as this period: normal for the season",
}


def conclusions(values: dict) -> list[str]:
    """The app's conclusions about a change in sales, in plain words, for the cloud writer to say as
    they are: it gets these instead of raw numbers to interpret, so it can't make up its own reasons."""
    if values["direction"] == "same":
        return ["Conclusion found by the app: sales have not really changed."]
    found = values["reasons"]
    lines = [f"Conclusion found by the app: sales went {values['direction']}."]
    if found:
        lines.append(f"Main reason found by the app: {MAIN_REASON[found[0]['kind']]}.")
    else:
        lines.append("Main reason found by the app: none. Stock, prices, alerts and last year don't explain it: say so plainly.")
    if values.get("last_year_compared"):
        lines.append(f"Last year: {LAST_YEAR[values['last_year_compared']]}.")
    lines.append("Say only these conclusions, the main reason first. Never add a reason of your own.")
    return lines


def reasons(facts: SalesFacts) -> list[dict]:
    """The reasons that fit, the main one first. Empty when no rule explains the change."""
    way = direction(facts.now, facts.before)
    if way == "same":
        return []
    found = []
    more_days_out = facts.out_now - facts.out_before
    if (way == "down" and more_days_out >= STOCK_OUT_DAYS) or (way == "up" and -more_days_out >= STOCK_OUT_DAYS):
        reason = {"kind": "out_of_stock" if way == "down" else "back_in_stock",
                  "days_now": facts.out_now, "days_before": facts.out_before}
        # Only when it's really a sum over more than one: a single part in a single branch needs no "across ...".
        for when, parts, branches in (
            ("now", facts.out_now_parts, facts.out_now_branches), ("before", facts.out_before_parts, facts.out_before_branches),
        ):
            if parts > 1:
                reason[f"days_{when}_parts"] = parts
            if branches > 1:
                reason[f"days_{when}_branches"] = branches
        found.append(reason)
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
