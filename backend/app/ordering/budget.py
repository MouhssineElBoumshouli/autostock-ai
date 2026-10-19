"""Staying within a budget: keep the lines that save the most lost profit per dirham spent.

For each line we estimate how many sales would be missed without it (demand above the stock we
would have), and how many with it. The difference times the margin per piece is what the line
saves; divided by what the line costs, it says how much each dirham spent is worth.
"""

import math
from dataclasses import dataclass


@dataclass
class BudgetLine:
    key: object  # whatever the caller uses to find the line again
    cost: int  # centimes
    value: float  # lost profit it prevents, in centimes


def expected_missed(mean: float, spread: float, available: float) -> float:
    """Average pieces customers want beyond `available`, when demand is roughly normal(mean, spread)."""
    if spread <= 0:
        return max(mean - available, 0.0)
    z = (available - mean) / spread
    density = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
    above = 0.5 * math.erfc(z / math.sqrt(2))  # chance demand is above `available`
    return spread * (density - z * above)


def missed_sales_prevented(mean: float, spread: float, available: float, ordered: int) -> float:
    return expected_missed(mean, spread, available) - expected_missed(mean, spread, available + ordered)


def line_value(prevented: float, unit_cost: int | None, sale_price: int | None) -> float:
    """Lost profit prevented, in centimes. No price or cost known = no margin we can count."""
    if unit_cost is None or sale_price is None:
        return 0.0
    return prevented * max(sale_price - unit_cost, 0)


def value_per_dirham(line: BudgetLine) -> float:
    return math.inf if line.cost <= 0 else line.value / line.cost


def apply_budget(lines: list[BudgetLine], budget: int | None) -> tuple[list[BudgetLine], list[BudgetLine]]:
    """(kept, cut). Best value per dirham first; a line that no longer fits is cut, and smaller
    lines after it may still fit. No budget = everything kept."""
    if budget is None:
        return list(lines), []
    kept, cut, spent = [], [], 0
    for line in sorted(lines, key=value_per_dirham, reverse=True):
        if spent + line.cost <= budget:
            kept.append(line)
            spent += line.cost
        else:
            cut.append(line)
    return kept, cut
