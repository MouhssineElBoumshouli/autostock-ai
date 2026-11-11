"""How much of Groq's free daily allowance is left, for Settings.

Groq's binding free limit is tokens a day (word pieces sent and written; openai/gpt-oss-120b: 200,000). Its
replies only say the requests left today, so the tokens are counted here from this shop's own answers since
midnight UTC (each online answer saves the tokens it used). Another program using the same key is not seen.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from app.ai import groq
from app.config import GROQ_MODEL
from app.models import AskedQuestion

TYPICAL_ANSWER_TOKENS = 3000  # measured on the 50 questions (docs/ask-real-assistant.md), until the shop has its own


def allowance(db: Session, organization_id: uuid.UUID) -> dict:
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    tokens = AskedQuestion.answer["tokens"].astext.cast(Integer)
    used, answers = db.execute(
        select(func.coalesce(func.sum(tokens), 0), func.count(tokens))
        .where(AskedQuestion.organization_id == organization_id, AskedQuestion.created_at >= since)
    ).one()
    per_day = groq.TOKENS_PER_DAY.get(GROQ_MODEL)
    per_answer = round(used / answers) if answers else TYPICAL_ANSWER_TOKENS
    left = None if per_day is None else max(0, per_day - int(used))
    seen = groq.last_limits
    return {
        "tokens_used_today": int(used), "tokens_per_day": per_day, "answers_today": int(answers),
        "answers_left_about": None if left is None else left // max(per_answer, 1),
        "requests_left_today": seen.get("requests_left_today"), "requests_per_day": seen.get("requests_per_day"),
    }
