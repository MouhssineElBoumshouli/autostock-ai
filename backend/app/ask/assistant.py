"""Ask your shop as an assistant. The local model only READS; the app thinks and writes.

1. Read: the keyword rule reads the question when it is sure; otherwise the local model turns it into
   one of the app's question types and filters, as strict JSON (app/ask/model_reader.py). A follow-up
   ("and in Rabat?", "et le mois dernier ?", "why?") is read as changes to the question before.
2. The app runs that question's read-only lookup. Comparisons, percentages and the reasons for a
   change (app/ask/why.py) are computed by the app.
3. Write: the app writes the answer with hand-written sentences in the question's language
   (app/ask/sentences/): always right, needs no AI. Darija questions are answered in Arabic.

Optional, off by default: the cloud writer (Groq, app/ai/cloud_writer.py), turned on by the owner in
Settings. It writes from the labeled facts only and never types a number: it writes each fact's label
([F1]) and the app puts the real number there (app/ask/labeled_facts.py). Each sentence is checked
before anyone sees it (app/ask/fact_check.py: no typed number, every label next to its own branch,
part and period), and the finished answer must be in the right language. If anything fails it tries
once more, told exactly what was wrong; if that fails too, or Groq can't be reached, the person gets
the app's own answer. The numbers used are always sent with it.
"""

import json
import uuid
from collections.abc import Generator, Iterator

from sqlalchemy.orm import Session

from app.ai import cloud_writer, llm
from app.ask.answer_language import in_language
from app.ask.answer_parts import shop_today
from app.ask.fact_check import WRONG_LANGUAGE, FactText, explained
from app.ask.keyword_rule import read_follow_up, read_with_rule
from app.ask.labeled_facts import labeled_facts
from app.ask.model_reader import read_with_model
from app.ask.question import NOT_SURE, Question, ShopWords
from app.ask.reply_language import DARIJA_WRITER_LANGUAGE, WRITER_LANGUAGE, is_darija, reply_language
from app.ask.sentences import fixed, written_answer
from app.ask.tools import Lookup, look_up
from app.ask.understand import shop_words
from app.ask.understood_line import heading

WRITER = """You write answers for an auto parts shop app. Today, for the shop, is {today}.
Answer the person's question in 2 to 4 short sentences, in {language}, using only the facts below.
- Never type a number or a date yourself. Write the fact's label instead, exactly like [F1]: the app puts
  the real number there. Comparisons and percentages are already facts: use their labels.
- Put each label right next to the branch, part or period it belongs to.
- Say what each number IS: pieces sold, pieces to order, pieces in stock, days out of stock. Never call
  pieces to order "sold". Lead with the direct answer to the question.
- Name parts without their numbers. Plain words, no tables, no markdown.
- Use the most useful facts, not all of them. If they don't answer the question, say what they do show.
- {money_rule}
Example: with the facts "[F1] Casablanca - Maarif · this period · pieces sold", "[F2] Casablanca - Maarif ·
change in pieces sold (down)", "[F3] Rabat - Agdal · this period · pieces sold", a good answer is:
"Casablanca - Maarif sold [F1] pieces this period, [F2] on the period before. Rabat - Agdal sold [F3] pieces."
The app's own answer, correct but plain, is: "{app_answer}"
The facts are about: {about}
Facts:
{facts}"""
RETRY = """The app did not show your answer: {problems}.
Write the whole answer again, in {language}, with the labels only."""
MONEY_SEEN = "Money amounts are in {currency}."
MONEY_HIDDEN = "This person doesn't see money: never mention prices, costs or sales values."


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
    app_language: str = "en", cloud: bool = False, model: str = llm.OLLAMA_MODEL,
) -> Iterator[dict]:
    """Events for the website, in order: {"type": "looking_up"}, {"type": "text"} pieces (after a
    {"type": "restart"}, the text so far is taken back), then one {"type": "done"}.
    `app_language` answers questions too short to tell their language; `cloud` lets Groq write."""
    shop = shop_words(db, organization_id)
    language = reply_language(question, app_language)
    understood, read_by = read(question, shop, earlier, model)
    lookups: list[Lookup] = []
    written_by, problems, retried = "app", [], False
    if understood is None:  # the website says so and suggests asking another way
        text = fixed("not_understood", language)
    elif understood.type == "cannot_answer":
        text = fixed("refusal", language)
    else:
        lookup = look_up(db, organization_id, currency, understood)
        lookups.append(lookup)
        yield {"type": "looking_up", "tool": lookup.tool, "filters": lookup.filters}
        text = written_answer(lookup.answer, language, currency)
        if cloud:
            writing = CloudWriting(db, organization_id, currency, question, language, shop, lookup, text)
            cloud_text = yield from writing.written()
            problems, retried = writing.problems, writing.retried
            if cloud_text:
                text, written_by = cloud_text, "cloud"
    if written_by == "app":
        yield {"type": "text", "text": text}
    yield {
        "type": "done",
        "text": text,
        "written_by": written_by,  # "app" or "cloud"
        "language": language,
        "cloud_problems": problems,  # why the cloud writer's answer wasn't shown, if it wasn't
        "retried": retried,
        "read_by": read_by,
        "question": {"type": understood.type, "filters": understood.filters()} if understood else None,
        "lookups": [_shown(lookup) for lookup in lookups],
    }


class CloudWriting:
    """One answer written by the cloud writer, checked sentence by sentence, with one second try."""

    def __init__(self, db, organization_id, currency, question, language, shop, lookup: Lookup, app_answer: str):
        understood = lookup.question
        self.facts = labeled_facts(lookup.answer, understood, currency, language)
        self.branches = shop.branches
        self.period = understood.period
        self.language = DARIJA_WRITER_LANGUAGE if is_darija(question) else WRITER_LANGUAGE[language]
        self.names = [*shop.branches, *(fact.part for fact in self.facts if fact.part)]
        writer = WRITER.format(
            today=shop_today(db, organization_id), language=self.language, app_answer=app_answer,
            money_rule=MONEY_SEEN.format(currency=currency) if currency else MONEY_HIDDEN,
            about=heading(understood), facts="\n".join(fact.line() for fact in self.facts),
        )
        self.messages = [{"role": "system", "content": writer},
                         {"role": "user", "content": f"{question}\n(Answer in {self.language}, with the labels.)"}]
        self.problems: list[str] = []
        self.retried = False

    def written(self) -> Generator[dict, None, str | None]:
        """The checked answer, or None (after a {"type": "restart"} if some of it was shown)."""
        text = FactText(self.facts, self.branches, self.period)
        try:
            written = yield from self._try(text)
            if text.wrong:
                self.retried = True
                if text.shown:
                    yield {"type": "restart"}
                reasons = "; ".join(dict.fromkeys(explained(problem) for problem in text.wrong))
                self.messages += [{"role": "assistant", "content": written},
                                  {"role": "user", "content": RETRY.format(problems=reasons, language=self.language)}]
                text = FactText(self.facts, self.branches, self.period)
                yield from self._try(text)
        except cloud_writer.WriterFailed as error:
            text.wrong = text.wrong or [f"(cloud writer failed: {error})"]
        self.problems = text.wrong
        if text.wrong or not text.shown.strip():
            if text.shown:
                yield {"type": "restart"}
            return None
        return text.shown.strip()

    def _try(self, text: FactText) -> Generator[dict, None, str]:
        """Lets the writing out sentence by sentence while it passes the check. Returns all it wrote."""
        written = ""
        for piece in cloud_writer.chat(self.messages):
            written += piece["text"]
            if out := text.add(piece["text"]):
                yield {"type": "text", "text": out}
            if text.wrong:
                return written
        if out := text.finish():
            yield {"type": "text", "text": out}
        if not text.wrong and text.shown and not in_language(text.shown, self.language, self.names):
            text.wrong = [f"{WRONG_LANGUAGE}{self.language}"]
        return written


def _shown(lookup: Lookup) -> dict:
    answer = lookup.answer
    return {
        "tool": lookup.tool, "filters": lookup.filters, "key": answer.key, "values": answer.values,
        "numbers": [number.model_dump() for number in answer.numbers],
    }


def as_line(event: dict) -> bytes:
    """One event per line (newline-delimited JSON), read by the website as it arrives."""
    return (json.dumps(event, ensure_ascii=False, default=str) + "\n").encode()
