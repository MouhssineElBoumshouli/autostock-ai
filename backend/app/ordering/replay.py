"""Replays past days one by one to compare two ways of ordering, on the same true demand.

Each day, in this order: deliveries ordered `delivery_days` ago arrive, the ordering rule may place
orders, then customers come. A customer who finds an empty shelf is a lost sale.
The rule only sees what a shop would have seen: past sales, with days the shelf was empty marked
unknown (NaN), never the true demand. Pure numpy: no database.
"""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from app.ordering.suggest import RECENT_DAYS, REVIEW_DAYS, SLOW_LOOKBACK_DAYS, HorizonForecast, Position, round_up_to_pack, suggest


@dataclass
class Today:
    day: int  # 0 = first replayed day
    on_hand: np.ndarray
    on_order: np.ndarray
    seen: np.ndarray  # rows x days so far: sales before today, NaN on empty-shelf days


@dataclass
class ReplayResult:
    days_out: int  # part-branch days the shelf was empty at opening or a customer left without it
    lost_pieces: int
    lost_money: int  # centimes, at sale price
    average_stock_value: float  # centimes at cost, end of day, averaged over the days
    orders: int  # order lines placed


Rule = Callable[[Today], np.ndarray | None]  # pieces to order per row, or None for "no order today"


def replay(
    demand: np.ndarray,
    past_seen: np.ndarray,
    start_stock: np.ndarray,
    delivery_days: np.ndarray,
    rule: Rule,
    unit_cost: np.ndarray,
    sale_price: np.ndarray,
) -> ReplayResult:
    """`demand`: true pieces wanted, rows x replayed days. `past_seen`: what the shop saw before."""
    rows, days = demand.shape
    delivery_days = delivery_days.astype(int)
    stock = start_stock.astype(float).copy()
    arriving = np.zeros((rows, days + int(delivery_days.max(initial=0)) + 1))
    seen = np.concatenate([past_seen, np.full((rows, days), np.nan)], axis=1)
    before = past_seen.shape[1]
    days_out = lost = lost_money = orders = 0
    stock_value = 0.0
    for day in range(days):
        stock += arriving[:, day]
        order = rule(Today(day, stock.copy(), arriving[:, day + 1 :].sum(axis=1), seen[:, : before + day]))
        if order is not None:
            placed = np.flatnonzero(order > 0)
            for i in placed:
                if delivery_days[i] == 0:
                    stock[i] += order[i]  # same-day delivery
                else:
                    arriving[i, day + delivery_days[i]] += order[i]
            orders += len(placed)
        sold = np.minimum(stock, demand[:, day])
        missed = demand[:, day] - sold
        out = (stock <= 0) | (missed > 0)
        days_out += int(out.sum())
        lost += int(missed.sum())
        lost_money += int((missed * sale_price).sum())
        seen[:, before + day] = np.where(out, np.nan, sold)
        stock -= sold
        stock_value += float((stock * unit_cost).sum())
    return ReplayResult(days_out, lost, lost_money, stock_value / days if days else 0.0, orders)


def minimum_rule(minimums: np.ndarray, pack_sizes: np.ndarray) -> Rule:
    """The usual rule, checked every day: when stock (counting what is on its way) is below the
    minimum, order back up to twice the minimum, in whole packs."""

    def decide(today: Today) -> np.ndarray:
        position = today.on_hand + today.on_order
        wanted = np.where(position < minimums, 2 * minimums - position, 0)
        return np.array([round_up_to_pack(int(q), int(p)) for q, p in zip(wanted, pack_sizes)])

    return decide


Forecaster = Callable[[np.ndarray], list[tuple[HorizonForecast, ...]]]  # seen history -> forecasts per row


def autostock_rule(forecaster: Forecaster, pack_sizes: np.ndarray, delivery_days: np.ndarray) -> Rule:
    """AutoStock's suggestions, made once every REVIEW_DAYS with forecasts remade from what was seen,
    and every suggested line approved as is."""

    def decide(today: Today) -> np.ndarray | None:
        if today.day % REVIEW_DAYS:
            return None
        forecasts = forecaster(today.seen)
        recent = np.nansum(today.seen[:, -RECENT_DAYS:], axis=1)
        lookback = np.nansum(today.seen[:, -SLOW_LOOKBACK_DAYS:], axis=1)
        return np.array([
            suggest(Position(int(today.on_hand[i]), int(today.on_order[i]), int(pack_sizes[i]), int(delivery_days[i]),
                             int(recent[i]), int(lookback[i]), forecasts[i])).quantity
            for i in range(len(forecasts))
        ])

    return decide
