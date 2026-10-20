"""How a question was read, in plain words, shown before every answer so the person can check it:
"I understood: Sales of brake pads · Rabat - Agdal · last month"."""

from app.ask.periods import LABELS, period_used
from app.ask.question import QUESTION_TYPES, Question

HEADINGS = {
    # type: (heading without a subject, heading with one)
    "sales_of": ("Sales", "Sales of {}"),
    "best_sellers": ("Best sellers", "Best sellers in {}"),
    "running_out": ("Running out soon", "Running out soon in {}"),
    "what_to_order": ("What to order", "What to order in {}"),
    "stock_of_part": ("Stock", "Stock of {}"),
    "dead_stock": ("Dead stock", "Dead stock in {}"),
    "open_alerts": ("Open alerts", "Open alerts for {}"),
    "late_deliveries": ("Late deliveries", "Late deliveries"),
    "forecast_of_part": ("Forecast for the next 30 days", "Forecast of {} for the next 30 days"),
    "sales_vs_last": ("Sales compared with the period before", "Sales of {} compared with the period before"),
}


def heading(question: Question) -> str:
    """"Sales of brake pads · Rabat - Agdal · last month" (the period used is shown even when not asked)."""
    subject = question.part or (f"{question.category} (category)" if question.category else None)
    without_subject, with_subject = HEADINGS[question.type]
    pieces = [with_subject.format(subject) if subject else without_subject]
    if question.branch:
        pieces.append(question.branch)
    if "period" in QUESTION_TYPES[question.type]:
        pieces.append(LABELS[period_used(question.type, question.period)])
    return " · ".join(pieces)


def understood_line(question: Question) -> str | None:
    """None when there is nothing to check: questions we can't answer, or when we weren't sure."""
    return f"I understood: {heading(question)}" if question.type in HEADINGS else None
