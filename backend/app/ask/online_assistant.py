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
from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.ai import groq
from app.ask.data_tools import Asker, run_tool, tool_specs
from app.ask.reply_language import is_darija, reply_language
from app.ask.tool_numbers import allowed_numbers, unknown_numbers
from app.models import Branch, Organization, SaleLine

MOST_STEPS = 5  # rounds of tool calls before the model must answer
EARLIER_TURNS = 3  # questions before this one, kept for follow-ups
RESULT_CHARACTERS = 6000  # a tool result sent to the model, at most (it is told when it was cut)
LANGUAGES = {"en": "English", "fr": "French", "ar": "Arabic"}
DARIJA = "Moroccan Darija, written the way the question is (Latin letters with 3/7/9 if it uses them, else Arabic letters)"

INSTRUCTIONS = """You are the assistant of the auto parts shop "{shop}" in the AutoStock app; you answer its staff.
Today is {today}. The newest sale imported is from {last_sale}.
Branches with sales: {branches}. "The shop", "le magasin" or no branch named = all branches (leave branch empty).
Parts are named "Type - Car" ("Filtre à huile - Dacia Logan"): put the type in "type", the car in "car", the brand
in "brand", never a sentence. An error gives the closest names: fix the call.
{money}
Rules:
1. Every number and every fact comes from the tools; never calculate, guess or add a trend, reason or stock fact
   you didn't look up (sales with compare gives the changes).
2. "this month" = the 1st to today; "October"/"last month" = the whole month, this year; "this week" = Monday to
   today; "last week" = the Monday-Sunday before. No period given: leave the dates empty. Dates YYYY-MM-DD.
   If the period goes past {last_sale}, say that sales after {last_sale} are not imported yet.
3. Answer in {language}, 1 to 3 short sentences, the direct answer first, with its period and branch. Only for
   "why" questions: call sales with compare (it adds last year, stock-out days and price) and give only the reasons
   it shows; if it shows none, say so. Plain text, no markdown, no list unless asked.
4. You only read. For actions say where: orders -> Orders page; alerts -> Alerts page; parts, prices, stock,
   sales -> Import page; suppliers -> Settings.
5. If the shop's data can't answer (customers, staff, salaries, rent, weather...), say so in one sentence, no number."""
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
        language=DARIJA if is_darija(question) else LANGUAGES[language],
    )


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
