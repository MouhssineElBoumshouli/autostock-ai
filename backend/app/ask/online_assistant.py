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
from app.ask.reply_language import is_darija, reply_language
from app.ask.tool_numbers import allowed_numbers, unknown_numbers
from app.models import Branch, Organization, Part, SaleLine

MOST_STEPS = 5  # rounds of tool calls before the model must answer
EARLIER_TURNS = 3  # questions before this one, kept for follow-ups
RESULT_CHARACTERS = 6000  # a tool result sent to the model, at most (it is told when it was cut)
LANGUAGES = {"en": "English", "fr": "French", "ar": "Arabic"}
DARIJA = "Moroccan Darija, written the way the question is (Latin letters with 3/7/9 if it uses them, else Arabic letters)"

INSTRUCTIONS = """You are the assistant of the auto parts shop "{shop}" in the AutoStock app; you answer its staff.
Today is {today}. The newest sale imported is from {last_sale}.
Periods: {periods}.
Branches with sales: {branches}. "The shop", "le magasin" or no branch named = all branches (leave branch empty).
Parts are named "Type - Car" ("Filtre à huile - Dacia Logan"). "type" takes one of the shop's types: {types}.
"car" is the make and model ("Peugeot 301"). "brand" is the part maker: {brands}. Never a sentence in a field.
An error gives the closest names: fix the call. totals (total_pieces...) answer the whole question; rows are details.
{money}
Rules:
1. Every number and every fact comes from the tools; never calculate, guess or add a trend, reason or stock fact
   you didn't look up (sales with compare gives the changes).
2. "this month" = the 1st to today; "October"/"last month" = the whole month, this year; "this week" = Monday to
   today; "last week" = the Monday-Sunday before. No period given: leave the dates empty. Dates YYYY-MM-DD.
   If the period goes past {last_sale}, say that sales after {last_sale} are not imported yet.
3. Answer in the question's language ({language} if unsure), 1 to 3 short sentences, the direct answer first, with its period and branch. Only for
   "why" questions: call sales with compare (it adds last year, stock-out days and price) and give only the reasons
   it shows; if it shows none, say so. Plain text, no markdown, no list unless asked.
4. You only read. For actions say where, with the page's name in the answer's language: Orders (fr "À commander",
   ar "ما يجب طلبه"); Alerts (fr "Alertes", ar "التنبيهات"); parts, prices, stock, sales: Import (fr "Importer",
   ar "استيراد"); suppliers: Settings (fr "Paramètres", ar "الإعدادات"). No order suggestion yet: say so.
5. Follow-ups ("and in September?", "et à Rabat ?"): keep the earlier question's part and branch, look it up again.
6. If the shop's data can't answer (customers, staff, salaries, rent, weather...), say so in one sentence, no number."""
MONEY_SEEN = "Money is in {currency}."
MONEY_HIDDEN = "This person must not see money: never mention prices, costs, values or margins."
FIX_NUMBERS = """These numbers are not in the tool results: {numbers}. Write the answer again using only numbers
the tools gave (call a tool if you need another number). Never compute one yourself."""


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
    for turn in earlier[-EARLIER_TURNS:]:
        messages += [{"role": "user", "content": turn.question},
                     {"role": "assistant", "content": f"{turn.answer}\n(Data used: {_compact(turn.facts)})"}]
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
        if not made_up and written:
            break
        if retried:
            raise AnswerRejected(made_up or ["(empty answer)"])
        retried = True
        messages += [{"role": "assistant", "content": written},
                     {"role": "user", "content": FIX_NUMBERS.format(numbers=", ".join(made_up) or "(none: the answer was empty)")}]
    else:
        raise AnswerRejected(["(no answer)"])
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
        brands=_names(db, organization_id, Part.brand),
        language=DARIJA if is_darija(question) else LANGUAGES[language],
    )


def periods(today: date) -> str:
    """The common periods with their exact dates, worked out by the app (models get dates wrong)."""
    monday = today - timedelta(days=today.weekday())
    month = today.replace(day=1)
    last_month_end = month - timedelta(days=1)
    return "; ".join(f"{name} {first.isoformat()} to {last.isoformat()}" for name, first, last in (
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
