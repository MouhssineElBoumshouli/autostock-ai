"""How many of one part to order for one branch. Pure math: no database, no language model.

Need  = expected sales while we wait (supplier delivery time + REVIEW_DAYS until the next order)
      + a safety cushion, sized so the shelf runs empty in only 1 period out of 10.
Order = need - on hand - already ordered, rounded up to whole packs, never below zero.

The cushion comes from the forecast's own range: its "high" end is the 90th percentile of past
misses, so (high - expected) is already a 90% cushion for that horizon. Uncertainty grows with the
square root of time, so it is scaled by sqrt(days / horizon) for the days we actually need.
"""

import math
from dataclasses import dataclass

REVIEW_DAYS = 7  # suggestions are made once a week
Z_90 = 1.2816  # 90% of a normal curve lies below mean + 1.2816 x spread
RECENT_DAYS = 28  # no sale in this many days = no recent sales
SLOW_LOOKBACK_DAYS = 90


@dataclass(frozen=True)
class HorizonForecast:
    horizon: int  # days
    quantity: float  # expected pieces over the horizon
    high: float  # 90th percentile


@dataclass(frozen=True)
class Position:
    """Everything known about one part in one branch on the day of the suggestion."""

    on_hand: int
    on_order: int
    pack_size: int
    delivery_days: int
    sold_last_28_days: int
    sold_last_90_days: int
    forecasts: tuple[HorizonForecast, ...]


@dataclass(frozen=True)
class Suggestion:
    quantity: int  # pieces to order (whole packs); 0 = nothing to order
    days_covered: int  # delivery days + review days
    expected: float  # pieces expected to sell over days_covered
    cushion: float  # extra pieces for a 90% chance of not running out
    need: int
    rule: str  # "forecast", "slow_out_of_stock" (one back on the shelf), or "slow_skip"


def days_covered(delivery_days: int) -> int:
    return delivery_days + REVIEW_DAYS


def pick_horizon(forecasts: tuple[HorizonForecast, ...], days: int) -> HorizonForecast:
    """The shortest forecast that covers `days`, or the longest one if none does."""
    ordered = sorted(forecasts, key=lambda f: f.horizon)
    return next((f for f in ordered if f.horizon >= days), ordered[-1])


def expected_and_cushion(forecasts: tuple[HorizonForecast, ...], days: int) -> tuple[float, float]:
    f = pick_horizon(forecasts, days)
    expected = f.quantity * days / f.horizon
    cushion = max(f.high - f.quantity, 0.0) * math.sqrt(days / f.horizon)
    return expected, cushion


def spread(forecasts: tuple[HorizonForecast, ...], days: int) -> float:
    """One standard deviation of demand over `days` (the cushion is Z_90 of them)."""
    return expected_and_cushion(forecasts, days)[1] / Z_90


def whole_need(expected: float, cushion: float) -> int:
    return math.ceil(round(expected + cushion, 6))  # round first: 3.0000000001 is 3, not 4


def round_up_to_pack(quantity: int, pack_size: int) -> int:
    pack = max(pack_size, 1)
    return math.ceil(quantity / pack) * pack if quantity > 0 else 0


def order_quantity(need: int, on_hand: int, on_order: int, pack_size: int) -> int:
    return round_up_to_pack(need - on_hand - on_order, pack_size)


def suggest(position: Position) -> Suggestion:
    days = days_covered(position.delivery_days)
    expected, cushion = expected_and_cushion(position.forecasts, days) if position.forecasts else (0.0, 0.0)
    need = whole_need(expected, cushion)
    if position.sold_last_28_days > 0:
        rule = "forecast"
    elif position.on_hand <= 0 and position.sold_last_90_days > 0:
        rule, need = "slow_out_of_stock", max(need, 1)  # someone still asks for it: one back on the shelf
    else:
        return Suggestion(0, days, expected, cushion, need, "slow_skip")
    quantity = order_quantity(need, position.on_hand, position.on_order, position.pack_size)
    return Suggestion(quantity, days, expected, cushion, need, rule)
