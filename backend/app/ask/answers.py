"""From a checked Question to an answer built by the app from read-only queries: one plain
sentence plus the real numbers it used. People who don't see money get no money numbers."""

import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.ask.answer_parts import Answer, Asked, shop_today
from app.ask.question import NOT_SURE, Question
from app.ask.sales_answers import best_sellers, sales_of, sales_vs_last
from app.ask.shop_answers import late_deliveries, open_alerts, what_to_order
from app.ask.stock_answers import dead_stock, forecast_of_part, running_out, stock_of_part

CANNOT_ANSWER_YET = "I can't answer that yet."
NOT_SURE_SENTENCE = "I'm not sure what you mean{by}. Did you mean one of these?"

ANSWERS: dict[str, Callable[[Asked], Answer]] = {
    "sales_of": sales_of,
    "best_sellers": best_sellers,
    "running_out": running_out,
    "what_to_order": what_to_order,
    "stock_of_part": stock_of_part,
    "dead_stock": dead_stock,
    "open_alerts": open_alerts,
    "late_deliveries": late_deliveries,
    "forecast_of_part": forecast_of_part,
    "sales_vs_last": sales_vs_last,
}


def answer(db: Session, organization_id: uuid.UUID, question: Question, currency: str | None) -> Answer:
    if question.type == NOT_SURE:
        return Answer(NOT_SURE_SENTENCE.format(by=f" by “{question.part}”" if question.part else ""))
    build = ANSWERS.get(question.type)
    if build is None:
        return Answer(CANNOT_ANSWER_YET)
    result = build(Asked(db, organization_id, question, shop_today(db, organization_id), currency))
    if currency is None:
        result.numbers = [number for number in result.numbers if number.unit != "money"]
    return result
