"""Sorts a part by how it sells, with the standard rule (Syntetos and Boylan):

- ADI: average number of days between two sales days. High = it sells rarely.
- CV²: how much the quantity on sales days varies (squared coefficient of variation). High = uneven.

smooth: often, even amounts · erratic: often, uneven amounts · slow: rarely, even amounts ·
lumpy: rarely, uneven amounts.
"""

import numpy as np

ADI_LIMIT = 1.32
CV2_LIMIT = 0.49
DEMAND_TYPES = ("smooth", "erratic", "slow", "lumpy", "no_sales")


def weekly_totals(history: np.ndarray) -> np.ndarray:
    """Sales per week, counted back from the last day. A week with unknown days is scaled up from
    its known days; a week with no known day is left out."""
    weeks = len(history) // 7
    days = history[len(history) - weeks * 7 :].reshape(weeks, 7)
    known = (~np.isnan(days)).sum(axis=1)
    totals = np.nansum(days, axis=1)
    return (totals * 7 / np.maximum(known, 1))[known > 0]


def adi_and_cv2(history: np.ndarray) -> tuple[float, float]:
    known = weekly_totals(history)
    sales = known[known > 0]
    if len(sales) == 0:
        return float("inf"), 0.0
    adi = len(known) / len(sales)
    cv2 = float((sales.std() / sales.mean()) ** 2)
    return adi, cv2


def demand_type(history: np.ndarray) -> str:
    adi, cv2 = adi_and_cv2(history)
    if adi == float("inf"):
        return "no_sales"
    if adi < ADI_LIMIT:
        return "smooth" if cv2 < CV2_LIMIT else "erratic"
    return "slow" if cv2 < CV2_LIMIT else "lumpy"
