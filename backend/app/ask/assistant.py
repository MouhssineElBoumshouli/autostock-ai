"""Ask your shop without the online assistant (Groq off, offline or out of its daily allowance).
The local model only READS; the app thinks and writes.

1. Read: the keyword rule reads the question when it is sure; otherwise the local model turns it into
   one of the app's question types and filters, as strict JSON (app/ask/model_reader.py). A follow-up
   ("and in Rabat?", "et le mois dernier ?", "why?") is read as changes to the question before.
2. The app runs that question's read-only lookup. Comparisons, percentages and the reasons for a
   change (app/ask/why.py) are computed by the app.
3. Write: the app writes the answer with hand-written sentences in the question's language
   (app/ask/sentences/): always right, needs no AI. Darija questions are answered in Arabic.
"""

import json
import re
import uuid
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.ai import llm
from app.ask.keyword_rule import read_follow_up, read_with_rule
from app.ask.model_reader import read_with_model
from app.ask.question import NOT_SURE, Question, ShopWords
from app.ask.reply_language import reply_language
from app.ask.sentences import fixed, written_answer
from app.ask.tools import Lookup, look_up
from app.ask.understand import shop_words


# A month or a year named in the question: the simple reader has no such periods, so it would answer
# another question ("compare septembre et octobre" read as this month vs the one before). It says so instead.
NAMED_PERIOD = re.compile(
    r"\b(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"(19|20)\d\d)\b|يناير|فبراير|مارس|أبريل|ابريل|ماي|يونيو|يوليوز|غشت|شتنبر|سبتمبر|أكتوبر|اكتوبر|نونبر|نوفمبر|دجنبر|ديسمبر",
    re.IGNORECASE)


def read(text: str, shop: ShopWords, earlier: Question | None, model: str) -> tuple[Question | None, str]:
    """The question understood, and by whom: "follow_up" and "rule" need no model. None if not understood."""
    if earlier:
        follow_up = read_follow_up(text, earlier, shop)
        if follow_up:
            return follow_up, "follow_up"
    by_rule = read_with_rule(text, shop)
    if by_rule.type != NOT_SURE:
        return by_rule, "rule"
    return read_with_model(text, shop, model, earlier), "model"


def converse(
    db: Session, organization_id: uuid.UUID, currency: str | None, question: str, earlier: Question | None,
    app_language: str = "en", model: str = llm.OLLAMA_MODEL, instead_of_online: bool = False,
) -> Iterator[dict]:
    """Events for the website, in order: {"type": "looking_up"}, one {"type": "text"}, one {"type": "done"}.
    `app_language` answers questions too short to tell their language. `instead_of_online`: the online assistant
    couldn't answer; then a question this simple version can't read gets "can't answer", never another answer."""
    shop = shop_words(db, organization_id)
    language = reply_language(question, app_language)
    understood, read_by = (None, "rule") if NAMED_PERIOD.search(question) else read(question, shop, earlier, model)
    if understood is None and read_by == "model" and not llm.is_on(model) and not instead_of_online:
        yield {"type": "ai_off"}  # the model failed to start: the website asks the keyword rule instead
        return
    lookups: list[Lookup] = []
    if instead_of_online and (understood is None or understood.type == "cannot_answer"):
        text, understood = fixed("simple_cannot", language), None
    elif understood is None:  # the website says so and suggests asking another way
        text = fixed("not_understood", language)
    elif understood.type == "cannot_answer":
        text = fixed("refusal", language)
    else:
        lookup = look_up(db, organization_id, currency, understood)
        lookups.append(lookup)
        yield {"type": "looking_up", "tool": lookup.tool, "filters": lookup.filters}
        text = written_answer(lookup.answer, language, currency)
    yield {"type": "text", "text": text}
    yield {
        "type": "done",
        "text": text,
        "written_by": "app",
        "language": language,
        "read_by": read_by,
        "question": {"type": understood.type, "filters": understood.filters()} if understood else None,
        "lookups": [_shown(lookup) for lookup in lookups],
    }


def _shown(lookup: Lookup) -> dict:
    answer = lookup.answer
    return {
        "tool": lookup.tool, "filters": lookup.filters, "key": answer.key, "values": answer.values,
        "numbers": [number.model_dump() for number in answer.numbers],
    }


def as_line(event: dict) -> bytes:
    """One event per line (newline-delimited JSON), read by the website as it arrives."""
    return (json.dumps(event, ensure_ascii=False, default=str) + "\n").encode()
