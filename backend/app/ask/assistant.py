"""Ask your shop as an assistant. The app does the thinking; the local model does two small jobs.

1. Read: the keyword rule reads the question when it is sure; otherwise the model turns it into one
   of the app's question types and filters, as strict JSON (app/ask/model_reader.py). A follow-up
   ("and in Rabat?", "why?") is read as changes to the question before and merged into it.
2. The app runs that question's read-only lookup itself. Comparisons and percentages are computed
   by the app and given as facts.
3. Write: the model writes 2 to 4 short sentences from those facts only, in the person's language.

Every number it writes is checked against the facts before the person sees it (app/ask/number_check.py).
Text goes to the screen one sentence at a time, each only once its numbers pass. If one fails, writing
stops and the website shows the app's own answer instead. The numbers used are always sent with it.
"""

import json
import re
import uuid
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.ai import llm
from app.ask.answer_parts import shop_today
from app.ask.keyword_rule import read_follow_up, read_with_rule
from app.ask.model_reader import read_with_model
from app.ask.number_check import AllowedNumbers
from app.ask.question import NOT_SURE, Question, ShopWords
from app.ask.tools import Lookup, for_the_model, look_up
from app.ask.understand import shop_words
from app.ask.words import words_of

SENTENCE_END = re.compile(r"[.!?؟:\n](?=\s)")
ARABIC_LETTER = re.compile(r"[؀-ۿ]")

WRITER = """You write answers for an auto parts shop app. Today, for the shop, is {today}.
Answer the person's question in 2 to 4 short sentences, in {language}, using only the facts below.
- Use only numbers that are in the facts. Comparisons and percentages are already computed there: copy them.
- Write every number in digits (12, not "twelve"). Plain words, no tables, no markdown. Lead with the answer.
- If the facts don't answer the question, say what they do show.
- {money_rule}
Facts:
{facts}"""
REFUSAL = """You write answers for an auto parts shop app. The app only reads the shop's stock, sales, alerts,
orders and suppliers. It never changes data or places orders (a person does that in the app), and it has no
data about customers or staff, nor about other topics.
In 1 or 2 short sentences, in {language}, politely say you can't help with this question and what you can
help with. Don't write any numbers."""
MONEY_SEEN = "Money amounts are in {currency}."
MONEY_HIDDEN = "This person doesn't see money: never mention prices, costs or sales values."
DARIJA_WORDS = set(words_of(
    "dyal dial kayn kayna chno chnou ach wach 3lach kifach ch7al chhal bzaf daba lyoum simana khassni khassna "
    "3tini bghit m9arna nkhaf mno kolchi ma kaytba3ch w f "
    "واش شحال ديال كيداير علاش كيفاش دابا بزاف هاد السيمانة خاصني عطيني بغيت باقي"
))
FRENCH_WORDS = set(words_of(
    "le la les des du est sont quoi quel quelle quelles combien pourquoi comment nous vous il reste ventes "
    "agence semaine mois neuf donne moi tout sur et une chez de"
))
DARIJA_SPELLING = re.compile(r"\b[a-z]*[379][a-z]+")  # "3lach", "m9arna", "ch7al": Darija written with digits


def reply_language(question: str) -> str:
    """The language to answer in, from the question itself."""
    words = set(words_of(question))
    darija = bool(words & DARIJA_WORDS) or bool(DARIJA_SPELLING.search(question.lower()))
    if ARABIC_LETTER.search(question):
        return "Moroccan Darija, in Arabic letters" if darija else "Arabic"
    if darija:
        return "Moroccan Darija, in Latin letters (like the question)"
    return "French" if words & FRENCH_WORDS else "English"


class CheckedText:
    """Holds the model's text until a sentence is complete, then lets it out only if every number in
    it is allowed. After the first wrong number it lets nothing more out."""

    def __init__(self, allowed: AllowedNumbers):
        self.allowed = allowed
        self.waiting = ""
        self.shown = ""
        self.wrong: list[str] = []

    def add(self, piece: str) -> str:
        self.waiting += piece
        ends = list(SENTENCE_END.finditer(self.waiting))
        return self._let_out(ends[-1].end()) if ends else ""

    def finish(self) -> str:
        return self._let_out(len(self.waiting))

    def _let_out(self, upto: int) -> str:
        if self.wrong:
            return ""
        ready, self.waiting = self.waiting[:upto], self.waiting[upto:]
        self.wrong = self.allowed.wrong_numbers(ready)
        if self.wrong:
            return ""
        self.shown += ready
        return ready


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
    model: str = llm.OLLAMA_MODEL,
) -> Iterator[dict]:
    """Events for the website, in order: {"type": "looking_up"}, {"type": "text"} pieces, then one
    {"type": "done"}. Or a single {"type": "ai_off"} when the model can't be reached."""
    shop = shop_words(db, organization_id)
    language = reply_language(question)
    understood, read_by = read(question, shop, earlier, model)
    lookups: list[Lookup] = []
    text = CheckedText(AllowedNumbers([], [question]))
    try:
        if understood is None:
            pass  # not understood: the website says so and suggests asking another way
        elif understood.type == "cannot_answer":
            yield from _written(text, [{"role": "system", "content": REFUSAL.format(language=language)},
                                       {"role": "user", "content": question}], model)
        else:
            lookup = look_up(db, organization_id, currency, understood)
            lookups.append(lookup)
            yield {"type": "looking_up", "tool": lookup.tool, "filters": lookup.filters}
            facts = for_the_model(lookup, currency)
            text.allowed = AllowedNumbers([json.loads(facts)], [question])
            money_rule = MONEY_SEEN.format(currency=currency) if currency else MONEY_HIDDEN
            writer = WRITER.format(today=shop_today(db, organization_id), language=language, money_rule=money_rule, facts=facts)
            yield from _written(text, [{"role": "system", "content": writer}, {"role": "user", "content": question}], model)
    except llm.ModelFailed:
        if not text.shown and not lookups:
            yield {"type": "ai_off"}
            return
        text.wrong = text.wrong or ["(the model stopped)"]
    if out := text.finish():
        yield {"type": "text", "text": out}
    yield {
        "type": "done",
        "checked": not text.wrong and bool(text.shown.strip()),
        "text": text.shown.strip(),
        "wrong_numbers": text.wrong,
        "read_by": read_by,
        "question": {"type": understood.type, "filters": understood.filters()} if understood else None,
        "lookups": [_shown(lookup) for lookup in lookups],
    }


def _written(text: CheckedText, messages: list[dict], model: str) -> Iterator[dict]:
    """The model's writing, let out sentence by sentence while its numbers pass."""
    for piece in llm.chat(messages, None, model):
        if "text" in piece and (out := text.add(piece["text"])):
            yield {"type": "text", "text": out}
        if text.wrong:
            return


def _shown(lookup: Lookup) -> dict:
    answer = lookup.answer
    return {
        "tool": lookup.tool, "filters": lookup.filters, "key": answer.key, "values": answer.values,
        "sentence": answer.sentence, "numbers": [number.model_dump() for number in answer.numbers],
    }


def as_line(event: dict) -> bytes:
    """One event per line (newline-delimited JSON), read by the website as it arrives."""
    return (json.dumps(event, ensure_ascii=False, default=str) + "\n").encode()

