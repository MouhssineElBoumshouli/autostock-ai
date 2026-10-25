"""Ask your shop as an assistant. The app does the thinking; the local model does two small jobs.

1. Read: the keyword rule reads the question when it is sure; otherwise the model turns it into one
   of the app's question types and filters, as strict JSON (app/ask/model_reader.py). A follow-up
   ("and in Rabat?", "why?") is read as changes to the question before and merged into it.
2. The app runs that question's read-only lookup itself. Comparisons and percentages are computed
   by the app and given as facts.
3. Write: the model writes 2 to 4 short sentences from those facts only, in the person's language.
   It never types a number: it writes each fact's label ([F1]), and the app puts the real number there
   (app/ask/labeled_facts.py).

Each sentence is checked before the person sees it (app/ask/fact_check.py): no number typed by the
model, and every label next to its own branch, part and period. Text goes to the screen one sentence
at a time. If one fails, writing stops and the website shows the app's own answer instead. The numbers
used are always sent with it.
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
from app.ask.fact_check import FactText
from app.ask.labeled_facts import labeled_facts
from app.ask.question import NOT_SURE, Question, ShopWords
from app.ask.tools import Lookup, look_up
from app.ask.understand import shop_words
from app.ask.words import words_of

LONGEST_ANSWER = 200  # word pieces (tokens): 2 to 4 sentences, and a model stuck repeating itself stops
ARABIC_LETTER = re.compile(r"[؀-ۿ]")

WRITER = """You write answers for an auto parts shop app. Today, for the shop, is {today}.
Answer the person's question in 2 to 4 short sentences, in {language}, using only the facts below.
- Never type a number or a date yourself. Write the fact's label instead, exactly like [F1]: the app puts
  the real number there. Comparisons and percentages are already facts: use their labels.
- Put each label right next to the branch, part or period it belongs to.
- Name parts without their numbers. Plain words, no tables, no markdown. Lead with the answer.
- Use the most useful facts, not all of them. If they don't answer the question, say what they do show.
- {money_rule}
Example: with the facts "[F1] Casablanca - Maarif · this period · pieces sold", "[F2] Casablanca - Maarif ·
change in pieces sold (down)", "[F3] Rabat - Agdal · this period · pieces sold", a good answer is:
"Casablanca - Maarif sold [F1] pieces this period, [F2] on the period before. Rabat - Agdal sold [F3] pieces."
Facts:
{facts}"""
REFUSAL = """You write answers for an auto parts shop app. The app only reads the shop's stock, sales, alerts,
orders and suppliers. It never changes data or places orders (a person does that in the app), and it has no
data about customers or staff, nor about other topics.
In 1 or 2 short sentences, in {language}, politely say you can't help with this question and what you can
help with. Don't write any numbers."""
MONEY_SEEN = "Money amounts are in {currency}."
NUMBER_STYLE = {"English": "en", "French": "fr"}  # how the app writes numbers; every other answer is in Arabic letters
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
# The small model can't write Darija (measured: 0 of 14 right): Darija questions get simple Arabic,
# which Moroccan readers understand, with Darija words where it knows them.
DARIJA_ANSWER = "simple Moroccan Arabic, in Arabic letters (Darija words are welcome)"
DARIJA_SPELLING = re.compile(r"\b[a-z]*[379][a-z]+")  # "3lach", "m9arna", "ch7al": Darija written with digits


def reply_language(question: str) -> str:
    """The language to answer in, from the question itself."""
    words = set(words_of(question))
    darija = bool(words & DARIJA_WORDS) or bool(DARIJA_SPELLING.search(question.lower()))
    if ARABIC_LETTER.search(question):
        return DARIJA_ANSWER if darija else "Arabic"
    if darija:
        return DARIJA_ANSWER
    return "French" if words & FRENCH_WORDS else "English"


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
    text = FactText([], shop.branches)
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
            facts = labeled_facts(lookup.answer, understood, currency, NUMBER_STYLE.get(language, "ar"))
            text = FactText(facts, shop.branches)
            money_rule = MONEY_SEEN.format(currency=currency) if currency else MONEY_HIDDEN
            writer = WRITER.format(today=shop_today(db, organization_id), language=language, money_rule=money_rule,
                                   facts="\n".join(fact.line() for fact in facts))
            asked = f"{question}\n(Answer in {language}, with the labels.)"
            yield from _written(text, [{"role": "system", "content": writer}, {"role": "user", "content": asked}], model)
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


def _written(text: FactText, messages: list[dict], model: str) -> Iterator[dict]:
    """The model's writing, let out sentence by sentence while it passes the check."""
    for piece in llm.chat(messages, model, LONGEST_ANSWER):
        if out := text.add(piece["text"]):
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

