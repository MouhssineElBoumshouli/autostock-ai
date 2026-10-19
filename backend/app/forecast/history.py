"""Turns sales lines into a clean daily demand table: one row per part per branch, one column per day.

A cell is NaN ("unknown") when the part had no stock that day or had not started selling yet:
zero sales then says nothing about how many people wanted it. Every other day without sales is 0.
"""

from datetime import date

import numpy as np

Sale = tuple[int, date, int]  # (row, day, quantity)
StockOutDays = tuple[int, date, date]  # (row, first day, last day)


def demand_matrix(sales: list[Sale], stock_outs: list[StockOutDays], rows: int, first_day: date, days: int) -> np.ndarray:
    demand = np.zeros((rows, days))
    for row, day, quantity in sales:
        index = (day - first_day).days
        if 0 <= index < days:
            demand[row, index] += quantity
    demand = np.clip(demand, 0, None)  # a day with more returns than sales sold nothing

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
