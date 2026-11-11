"""Stock that doesn't match sales, for one part in one branch. At most one per part and branch, the
clearest first:
1. Negative stock: fewer than zero on the shelf is impossible, so the count is wrong.
2. Sold while stock was 0: sales recorded on a day that started and ended with nothing on the shelf.
3. Stock frozen: the number has not moved for 14 days or more while sales continued (theft, a
   counting error, or sales not taken off the stock).
"""

import numpy as np

from app.alerts.problem import Problem, day_label, pieces
from app.alerts.shop_data import ShopData

LOOK_BACK_DAYS = 7  # "sold while 0" looks at the last week
MIN_FROZEN_DAYS = 14
MIN_FROZEN_SOLD = 3  # one or two pieces can be a return or a late entry; three sold is a pattern


def stock_problems(data: ShopData, end: int) -> list[Problem]:
    # If no stock moved anywhere in the shop lately, the shop simply hasn't sent new stock numbers:
    # that is not a problem with one part, so "frozen" is not judged.
    shop_updates_stock = bool(data.stock_changed_days[max(end - LOOK_BACK_DAYS + 1, 0) : end + 1].any())
    problems = []
    for row in range(len(data.keys)):
        shelf, sold = data.shelf[row, : end + 1], data.sold[row, : end + 1]
        if np.isnan(shelf[end]):
            continue
        problem = _negative(data, row, shelf) or _sold_at_zero(data, row, shelf, sold)
        if problem is None and shop_updates_stock:
            problem = _frozen(data, row, shelf, sold)
        if problem is not None:
            problems.append(problem)
    return problems


def _negative(data: ShopData, row: int, shelf: np.ndarray) -> Problem | None:
    end = len(shelf) - 1
    if shelf[end] >= 0:
        return None
    first = end
    while first > 0 and shelf[first - 1] < 0:
        first -= 1
    quantity = int(shelf[end])
    at_stake = -quantity * data.money_per_piece(row, sales=False)
    sentence = f"Stock shows {quantity} since {day_label(data.day(first))}: below zero is impossible, so the count is wrong."
    return Problem(*data.keys[row], "negative_stock", data.day(first), at_stake, sentence, {"quantity": quantity})


def _sold_at_zero(data: ShopData, row: int, shelf: np.ndarray, sold: np.ndarray) -> Problem | None:
    end = len(shelf) - 1
    days = [
        d
        for d in range(max(end - LOOK_BACK_DAYS + 1, 1), end + 1)
        if sold[d] > 0 and shelf[d - 1] <= 0 and shelf[d] <= 0  # NaN (unknown) compares False
    ]
    if not days:
        return None
    count = int(sold[days].sum())
    at_stake = count * data.money_per_piece(row, sales=False)
    on_days = "1 day" if len(days) == 1 else f"{len(days)} days"
    sentence = f"Sold {pieces(count)} on {on_days} since {day_label(data.day(days[0]))} while stock showed 0."
    return Problem(*data.keys[row], "sold_at_zero", data.day(days[0]), at_stake, sentence, {"sold": count, "days": len(days)})


def _frozen(data: ShopData, row: int, shelf: np.ndarray, sold: np.ndarray) -> Problem | None:
    end = len(shelf) - 1
    if shelf[end] <= 0:
        return None
    last_change = end
    while last_change > 0 and shelf[last_change - 1] == shelf[end]:
        last_change -= 1  # stops at the first day of the current number (or the first day known)
    unchanged_days = end - last_change
    count = int(sold[last_change + 1 :].sum())
    if unchanged_days < MIN_FROZEN_DAYS or count < MIN_FROZEN_SOLD:
        return None
    quantity = int(shelf[end])
    at_stake = count * data.money_per_piece(row, sales=False)
    since = data.day(last_change + 1)
    sentence = f"Stock stuck at {quantity} since {day_label(since)} while {pieces(count)} were sold."
    numbers = {"quantity": quantity, "sold": count, "unchanged_days": unchanged_days}
    return Problem(*data.keys[row], "stock_frozen", since, at_stake, sentence, numbers)
