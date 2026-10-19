"""One plain sentence per suggestion line: why this part, why this number.

English for now. The numbers are also stored on each line, so the website can build the same
sentence in French or Arabic later (as the forecast screens do)."""

from app.ordering.suggest import Suggestion


def selling_rate(expected: float, days: int) -> str:
    weekly = expected * 7 / days if days else 0.0
    if weekly >= 1:
        return f"Sells about {round(weekly)} a week"
    monthly = weekly * 30 / 7
    if monthly >= 1:
        return f"Sells about {round(monthly)} a month"
    return "Sells less than 1 a month"


def reason(s: Suggestion, delivery_days: int, on_hand: int, on_order: int, pack_size: int, sold_last_90_days: int) -> str:
    if s.rule == "slow_out_of_stock":
        return f"Out of stock, sold {sold_last_90_days} in the last 90 days, no sale in 4 weeks: order {s.quantity} to have it on the shelf."
    if s.rule == "slow_skip":
        return "No sale in 4 weeks: not ordered."
    stock = f"{on_hand} left" + (f", {on_order} already ordered" if on_order else "")
    packs = f" (packs of {pack_size})" if pack_size > 1 else ""
    return (
        f"{selling_rate(s.expected, s.days_covered)}, supplier takes {delivery_days} days, {stock}: "
        f"order {s.quantity}{packs} to cover the next {s.days_covered} days with a safety cushion of {round(s.cushion)}."
    )
