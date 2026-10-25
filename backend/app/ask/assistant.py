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
at a time. Once finished, the answer must be in the question's language (app/ask/answer_language.py).
If anything fails, the writer tries once more, told exactly what was wrong (what was shown is taken
back first). If that fails too, the website shows the app's own answer instead, in the person's own
app language. The numbers used are always sent with it.
"""

import json
import re
import uuid
from collections.abc import Generator, Iterator

from sqlalchemy.orm import Session

from app.ai import llm
from app.ask.answer_parts import shop_today
from app.ask.keyword_rule import read_follow_up, read_with_rule
from app.ask.model_reader import read_with_model
from app.ask.answer_language import in_language
from app.ask.fact_check import WRONG_LANGUAGE, FactText, explained
from app.ask.labeled_facts import labeled_facts
from app.ask.question import NOT_SURE, Question, ShopWords
from app.ask.tools import Lookup, look_up
from app.ask.understood_line import heading
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
The facts are about: {about}
Facts:
{facts}"""
REFUSAL = """You write answers for an auto parts shop app. The app only reads the shop's stock, sales, alerts,
orders and suppliers. It never changes data or places orders (a person does that in the app), and it has no
data about customers or staff, nor about other topics.
In 1 or 2 short sentences, in {language}, politely say you can't help with this question and what you can
help with. Don't write any numbers."""
RETRY = """The app did not show your answer: {problems}.
Write the whole answer again, in {language}, with the labels only."""
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
    """Events for the website, in order: {"type": "looking_up"}, {"type": "text"} pieces (after a
    {"type": "restart"}, the text so far is taken back), then one {"type": "done"}. Or a single
    {"type": "ai_off"} when the model can't be reached."""
    shop = shop_words(db, organization_id)
    language = reply_language(question)
    understood, read_by = read(question, shop, earlier, model)
    lookups: list[Lookup] = []
    text = FactText([], shop.branches)
    retried = False
    try:
        if understood is not None:  # not understood: the website says so and suggests asking another way
            if understood.type == "cannot_answer":
                facts: list = []
                messages = [{"role": "system", "content": REFUSAL.format(language=language)},
                            {"role": "user", "content": question}]
            else:
                lookup = look_up(db, organization_id, currency, understood)
                lookups.append(lookup)
                yield {"type": "looking_up", "tool": lookup.tool, "filters": lookup.filters}
                facts = labeled_facts(lookup.answer, understood, currency, NUMBER_STYLE.get(language, "ar"))
                money_rule = MONEY_SEEN.format(currency=currency) if currency else MONEY_HIDDEN
                writer = WRITER.format(today=shop_today(db, organization_id), language=language, money_rule=money_rule,
                                       about=heading(understood), facts="\n".join(fact.line() for fact in facts))
                messages = [{"role": "system", "content": writer},
                            {"role": "user", "content": f"{question}\n(Answer in {language}, with the labels.)"}]
            names = [*shop.branches, *(fact.part for fact in facts if fact.part)]
            text = FactText(facts, shop.branches, understood.period)
            written = yield from _written(text, messages, model)
            _check_language(text, language, names)
            if text.wrong:
                # One second try, told exactly what was wrong. What was already shown is taken back first.
                retried = True
                if text.shown:
                    yield {"type": "restart"}
                problems = "; ".join(dict.fromkeys(explained(problem) for problem in text.wrong))
                messages += [{"role": "assistant", "content": written},
                             {"role": "user", "content": RETRY.format(problems=problems, language=language)}]
                text = FactText(facts, shop.branches, understood.period)
                yield from _written(text, messages, model)
                _check_language(text, language, names)
    except llm.ModelFailed:
        if not text.shown and not lookups:
            yield {"type": "ai_off"}
            return
        text.wrong = text.wrong or ["(the model stopped)"]
    yield {
        "type": "done",
        "checked": not text.wrong and bool(text.shown.strip()),
        "text": "" if text.wrong else text.shown.strip(),  # when blocked, the person sees the app's own answer
        "wrong_numbers": text.wrong,
        "retried": retried,
        "read_by": read_by,
        "question": {"type": understood.type, "filters": understood.filters()} if understood else None,
        "lookups": [_shown(lookup) for lookup in lookups],
    }


def _written(text: FactText, messages: list[dict], model: str) -> Generator[dict, None, str]:
    """The model's writing, let out sentence by sentence while it passes the check. Returns all it wrote."""
    written = ""
    for piece in llm.chat(messages, model, LONGEST_ANSWER):
        written += piece["text"]
        if out := text.add(piece["text"]):
            yield {"type": "text", "text": out}
        if text.wrong:
            return written
    if out := text.finish():
        yield {"type": "text", "text": out}
    return written


def _check_language(text: FactText, language: str, names: list[str]) -> None:
    """A finished answer in another language than the question's counts as blocked."""
    if not text.wrong and text.shown and not in_language(text.shown, language, names):
        text.wrong = [f"{WRONG_LANGUAGE}{language}"]


def _shown(lookup: Lookup) -> dict:
    answer = lookup.answer
    return {
        "tool": lookup.tool, "filters": lookup.filters, "key": answer.key, "values": answer.values,
        "sentence": answer.sentence, "numbers": [number.model_dump() for number in answer.numbers],
    }


def as_line(event: dict) -> bytes:
    """One event per line (newline-delimited JSON), read by the website as it arrives."""
    return (json.dumps(event, ensure_ascii=False, default=str) + "\n").encode()

