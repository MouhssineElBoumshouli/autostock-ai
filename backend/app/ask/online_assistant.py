"""Ask your shop with the online assistant: Groq's free model thinks, the app's read-only tools give the facts.

1. The model gets the question, the conversation so far, today's date, the last imported sale and the shop's
   branches, part types and cars. It asks for tools (several if needed: app/ask/data_tools), always scoped to
   the asker's shop; people who don't see money never get money.
2. It answers in the question's language, the most useful fact first.
3. The app checks every number in the answer against the tool results (app/ask/tool_numbers.py). A number
   no tool gave -> the model is told which, and writes again once; still wrong -> AnswerRejected, and the
   page gets the app's own answer instead. The lookups used are shown under "Based on".

It never changes data: the tools only read, in a read-only database transaction.
"""

import json
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.ai import groq
from app.ask.data_tools import Asker, run_tool, tool_specs
from app.ask.data_tools.context import TYPE_NAME
from app.ask.answer_dates import in_words
from app.ask.reply_language import ARABIC_LETTER, ENGLISH_WORDS, FRENCH_WORDS, is_darija, reply_language
from app.ask.words import words_of
from app.ask.tool_numbers import allowed_numbers, missing_counts, unknown_numbers, wrong_direction
from app.models import Branch, Organization, Part, SaleLine

MOST_STEPS = 5  # rounds of tool calls before the model must answer
EARLIER_TURNS = 3  # questions before this one, kept for follow-ups
RESULT_CHARACTERS = 6000  # a tool result sent to the model, at most (it is told when it was cut)
LANGUAGES = {"en": "English", "fr": "French", "ar": "Arabic"}
# The app's page names in each language (frontend/src/i18n), so an answer names them the way the person sees them.
PAGES = {
    "en": {"orders": "What to order", "alerts": "Alerts", "files": "Import", "settings": "Settings"},
    "fr": {"orders": "À commander", "alerts": "Alertes", "files": "Importer", "settings": "Paramètres"},
    "ar": {"orders": "ما يجب طلبه", "alerts": "التنبيهات", "files": "استيراد", "settings": "الإعدادات"},
}
DARIJA = "Moroccan Darija, written the way the question is (Latin letters with 3/7/9 if it uses them, else Arabic letters)"

INSTRUCTIONS = """Assistant of the auto parts shop "{shop}" (AutoStock app). Today: {today}. Sales imported up to {last_sale}.
Periods: {periods}. Branches: {branches} (none named = whole shop: leave branch empty).
Part fields: type = one of: {types}; or a general word for all its types ("Batterie"). car = make and model. brand =
part maker. Never a sentence in a field. {money}
- Numbers and facts only from tools; never compute or guess. total_* answer the question; rows are details.
- No period asked: leave dates empty (last 30 days of data) and say which days. Sales come with the period before.
- Why sales changed: why_sales; say its direction and only its reasons. Will I run out, what to order (first),
  which supplier first: always look up running_out and follow its order_first_from (never your own ranking); give its
  counts (at_risk part-branches: different_parts in branches, out_now already at zero) and name its first 3 rows. Money in stock: stock. Not
  selling: stock only=dead. stock_outs = past days without stock. Best-selling "pièces"/parts: group_by part.
- A question is never an action: answer it. Only doing something (order, change, delete) is not possible: say where
  in the app: orders "{orders}", alerts "{alerts}", files "{files}", suppliers "{settings}".
- Data the shop doesn't have (customers, salaries, weather...): say so, no number.
- Answer in {language} only: 1 to 3 short plain sentences, the direct answer first, with its main numbers and
  period. Name a branch only if the person did; otherwise it is the whole shop."""
MONEY_SEEN = "Money is in {currency}."
MONEY_HIDDEN = "This person must not see money: never mention prices, costs, values or margins."
FIX_NUMBERS = """Not shown, fix it: {numbers}. (A number listed is not in the tool results.) Write the answer again,
with only numbers the tools gave (call a tool if you need another one), never one you computed."""


class AnswerRejected(Exception):
    """The answer still had numbers no tool gave after the second try."""

    def __init__(self, numbers: list[str]):
        super().__init__(", ".join(numbers))
        self.numbers = numbers


@dataclass
class EarlierTurn:
    question: str
    answer: str
    facts: list  # the tool results it used


def answer(
    db: Session, organization_id: uuid.UUID, currency: str | None, question: str, earlier: list[EarlierTurn],
    app_language: str, today: date, model: str = groq.GROQ_MODEL,
) -> Iterator[dict]:
    """Events for the website: {"type": "looking_up"} per tool call, one {"type": "text"} and one
    {"type": "done"}. Raises groq.GroqFailed or AnswerRejected before any text is sent."""
    started = time.perf_counter()
    db.execute(text("SET TRANSACTION READ ONLY"))  # the tools can only read, whatever they run
    last_sale = db.scalar(select(func.max(SaleLine.sold_on)).where(SaleLine.organization_id == organization_id))
    asker = Asker(db, organization_id, today, last_sale, currency)
    language = reply_language(question, app_language)
    messages = [{"role": "system", "content": instructions(asker, question, language)}]
    turns = earlier[-EARLIER_TURNS:]
    if turns:  # the facts behind earlier answers, apart from them so the model never copies the format
        messages.append({"role": "system", "content": f"Tool results behind the earlier answers: {_compact([t.facts for t in turns])}"})
    for turn in turns:
        messages += [{"role": "user", "content": turn.question}, {"role": "assistant", "content": turn.answer}]
    messages.append({"role": "user", "content": question})
    tools = tool_specs(asker.sees_money)
    lookups: list[dict] = []
    tokens, retried = 0, False
    for step in range(MOST_STEPS + 2):
        reply = groq.complete(messages, tools if step < MOST_STEPS else [], model)
        tokens += reply.tokens
        calls = reply.message.get("tool_calls") or []
        if calls:
            messages.append({"role": "assistant", "content": reply.message.get("content") or "", "tool_calls": calls})
            for call in calls:
                lookup = _looked_up(asker, call)
                lookups.append(lookup)
                yield {"type": "looking_up", "tool": lookup["tool"], "filters": lookup["filters"]}
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": _compact(lookup["data"])})
            continue
        written = (reply.message.get("content") or "").replace("**", "").strip()  # plain text on the page
        allowed = allowed_numbers([lookup["data"] for lookup in lookups] + [turn.facts for turn in earlier],
                                  [question], [today, *([last_sale] if last_sale else [])])
        made_up = unknown_numbers(written, allowed)
        wrong_way = wrong_direction(written, [lookup["data"] for lookup in lookups])
        if wrong_way:
            made_up.append(f"(the change went {wrong_way}, the answer says the opposite)")
        missing = missing_counts(written, [lookup["data"] for lookup in lookups])
        if missing:
            made_up.append(f"(say the counts {missing} and name the first parts at risk)")
        if wrong_language(written, language, is_darija(question)):
            made_up.append(f"(the answer must be in {LANGUAGES[language]})")
        if not made_up and written:
            break
        if retried:
            raise AnswerRejected(made_up or ["(empty answer)"])
        retried = True
        messages += [{"role": "assistant", "content": written},
                     {"role": "user", "content": FIX_NUMBERS.format(numbers=", ".join(made_up) or "(none: the answer was empty)")}]
    else:
        raise AnswerRejected(["(no answer)"])
    written = in_words(written, language, today)  # "2026-10-01" -> "1er octobre"
    yield {"type": "text", "text": written}
    yield {
        "type": "done", "text": written, "written_by": "groq", "language": language, "read_by": "groq",
        "question": None, "retried": retried, "tokens": tokens,
        "seconds": round(time.perf_counter() - started, 2), "model": model,
        "lookups": [{key: lookup[key] for key in ("tool", "filters", "key", "values", "numbers")} for lookup in lookups],
        "facts": [lookup["data"] for lookup in lookups],  # kept for follow-ups: their numbers stay allowed
    }


def instructions(asker: Asker, question: str, language: str) -> str:
    db, organization_id = asker.db, asker.organization_id
    shop = db.scalar(select(Organization.name).where(Organization.id == organization_id))
    sold = select(SaleLine.id).where(SaleLine.organization_id == organization_id, SaleLine.branch_id == Branch.id).exists()
    branches = db.execute(select(Branch.name, sold).where(Branch.organization_id == organization_id).order_by(Branch.name)).all()
    return INSTRUCTIONS.format(
        shop=shop, today=f"{asker.today:%A %Y-%m-%d}",
        last_sale=asker.last_sale_day.isoformat() if asker.last_sale_day else "never (no sales imported yet)",
        branches=", ".join(name for name, has_sales in branches if has_sales) or "none yet",
        money=MONEY_SEEN.format(currency=asker.currency) if asker.sees_money else MONEY_HIDDEN,
        periods=periods(asker.today), types=_names(db, organization_id, TYPE_NAME),
        language=DARIJA if is_darija(question) else LANGUAGES[language], **PAGES[language],
    )


def wrong_language(text: str, language: str, darija: bool) -> bool:
    """True when an answer is plainly in another language than the question's (part names don't count much:
    it takes 3 words of the other language and twice as many as of the right one)."""
    words = words_of(text)
    french, english = sum(word in FRENCH_WORDS for word in words), sum(word in ENGLISH_WORDS for word in words)
    if language == "en":
        return french >= 3 and french > 2 * english
    if language == "fr":
        return english >= 3 and english > 2 * french
    return not darija and not ARABIC_LETTER.search(text)


def periods(today: date) -> str:
    """The common periods with their exact dates, worked out by the app (models get dates wrong)."""
    monday = today - timedelta(days=today.weekday())
    month = today.replace(day=1)
    last_month_end = month - timedelta(days=1)
    return "; ".join(f"{name} {first.isoformat()}..{last.isoformat()}" for name, first, last in (
        ("this week", monday, today), ("last week", monday - timedelta(days=7), monday - timedelta(days=1)),
        ("this month", month, today), ("last month", last_month_end.replace(day=1), last_month_end),
        ("this year", today.replace(month=1, day=1), today), ("yesterday", today - timedelta(days=1), today - timedelta(days=1))))


def _names(db: Session, organization_id: uuid.UUID, column, most: int = 80) -> str:
    names = sorted({name for name in db.scalars(select(column).where(Part.organization_id == organization_id).distinct()) if name})
    return ", ".join(names[:most]) + (", ..." if len(names) > most else "") or "(none)"


def _looked_up(asker: Asker, call: dict) -> dict:
    name = call.get("function", {}).get("name", "")
    try:
        args = json.loads(call.get("function", {}).get("arguments") or "{}")
    except ValueError:
        args = None
    result = run_tool(asker, name, args)
    return {"tool": name, "filters": result.heading, "key": name, "values": {},
            "numbers": [number.model_dump() for number in result.shown], "data": result.data}


def _compact(value: object) -> str:
    written = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    return written if len(written) <= RESULT_CHARACTERS else written[:RESULT_CHARACTERS] + "…(cut)"
