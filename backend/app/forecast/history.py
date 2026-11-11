"""Turns sales lines into a clean daily demand table: one row per part per branch, one column per day.

A cell is NaN ("unknown") when the part had no stock that day or had not started selling yet:
zero sales then says nothing about how many people wanted it. Every other day without sales is 0.

Sales are read as one short list of days per part and branch (added up by the database), not one
Python row per sales line: a big shop has tens of millions of sales lines.
"""

import uuid
from datetime import date

import numpy as np
from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.models import Part, SaleLine

Key = tuple[uuid.UUID, uuid.UUID]  # (part_id, branch_id)
DaySales = tuple[np.ndarray, np.ndarray]  # day numbers (date.toordinal()), and a quantity for each
StockOutDays = tuple[int, date, date]  # (row, first day, last day)
DAY_ZERO = date(1, 1, 1)  # date.toordinal() counts from here (day 1)
READ_AT_A_TIME = 5000


def read_daily_sales(db: Session, organization_id: uuid.UUID, until: date | None = None) -> dict[Key, DaySales]:
    """Every sales line (returns as negative quantities) of every active part in every branch, up
    to `until` if given: (day numbers, quantities), a day appearing once per line. sales_table adds
    up each day; doing it here instead would make PostgreSQL group tens of millions of lines twice."""
    filters = [SaleLine.organization_id == organization_id, Part.is_active]
    if until is not None:
        filters.append(SaleLine.sold_on <= until)
    day_number = SaleLine.sold_on - literal(DAY_ZERO) + 1
    rows = db.execute(
        select(SaleLine.part_id, SaleLine.branch_id, func.array_agg(day_number), func.array_agg(SaleLine.quantity))
        .join(Part, Part.id == SaleLine.part_id)
        .where(*filters)
        .group_by(SaleLine.part_id, SaleLine.branch_id)
        .execution_options(yield_per=READ_AT_A_TIME)
    )
    return {(part, branch): (np.array(days, dtype=np.int32), np.array(quantities, dtype=np.int32)) for part, branch, days, quantities in rows}


def first_and_last_day(sales: dict[Key, DaySales]) -> tuple[date, date]:
    days = [(days.min(), days.max()) for days, _ in sales.values()]
    return date.fromordinal(int(min(first for first, _ in days))), date.fromordinal(int(max(last for _, last in days)))


def sales_table(sales: dict[Key, DaySales], keys: list[Key], first_day: date, days: int) -> np.ndarray:
    """Pieces sold per day (lines of one day added up, returns taken off), one row per key (0 for a
    key without sales). Days outside the table are left out."""
    table = np.zeros((len(keys), days))
    start = first_day.toordinal()
    for row, key in enumerate(keys):
        if key in sales:
            day_numbers, quantities = sales[key]
            inside = (day_numbers >= start) & (day_numbers < start + days)
            np.add.at(table[row], day_numbers[inside] - start, quantities[inside])
    return table


def demand_matrix(sold: np.ndarray, stock_outs: list[StockOutDays], first_day: date) -> np.ndarray:
    """`sold`: pieces sold per row per day, returns taken off (see sales_table)."""
    demand = np.clip(sold, 0, None)  # a day with more returns than sales sold nothing
    rows, days = demand.shape

    for row in range(rows):
        sold_days = np.flatnonzero(demand[row] > 0)
        first_sale = sold_days[0] if len(sold_days) else days
        demand[row, :first_sale] = np.nan

    for row, first, last in stock_outs:
        start = max((first - first_day).days, 0)
        end = min((last - first_day).days, days - 1)
        if start <= end:
            demand[row, start : end + 1] = np.nan
    return demand
