"""Ask your shop as an assistant: the local model looks things up with the read-only tools (several
if needed), then writes the answer in the person's language.

The model may write the answer, but every number in it is checked against what was looked up before
the person sees it (app/ask/number_check.py). Text goes to the screen one sentence at a time, each
sentence only once its numbers pass. If one number fails, writing stops and the website shows the
app's own answers from the same lookups instead. The numbers used are always sent with the answer.
"""

import json
import re
import uuid
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.ai import llm
from app.ask.answer_parts import shop_today
from app.ask.number_check import AllowedNumbers
from app.ask.tools import MOST_CALLS, Lookup, for_the_model, look_up, shop_names, tool_specs
from app.ask.understand import shop_words
from app.ask.words import words_of

ROUNDS = 3  # look up, maybe look up more, then answer
EARLIER_TURNS = 3
SENTENCE_END = re.compile(r"[.!?؟:\n](?=\s)")
ARABIC_LETTER = re.compile(r"[؀-ۿ]")

INSTRUCTIONS = """You are the assistant of an auto parts shop. You answer questions from the shop's people about
their stock, sales, alerts, orders and suppliers. Today, for the shop, is {today}.
{shop_names}

Rules:
- Write every number in digits (12, not "twelve").
- Every number you write must come from a tool result for this question. Numbers from earlier messages
  are not enough: look them up again. If the tools don't give a number, don't write one.
- For any question about the shop, call a tool before answering. Never say there is no data without
  looking it up first. Part names may be in French, Arabic or Darija: pass them as written, the app
  understands them.
- Call as many tools as the question needs. For open questions ("what's going on", "how are we doing",
  "what should I worry about") use today_briefing. For "why did sales of X change" use explain_part_change.
- Only use the filters (part, category, branch, period) the person asked for. Leave the others out.
- A follow-up like "and in Rabat?" or "why?" is about the previous question: keep its part, category and
  period, change only what the person changed.
- Reply in {language}.
- Be short and clear: 2 to 5 sentences in plain words, no tables, no markdown. Lead with the answer.
- You can only read the shop's data. If asked to change data or place an order, say a person does that
  in the app. If asked about customers, staff, or anything else than the shop's stock and sales, say
  politely that you can't help with that. Don't call tools for those.
- {money_rule}"""
RECHECK = """The app checked your answer: these numbers are not in what you looked up: {numbers}.
Look them up with the tools, then answer again, in {language}. Don't mention this check."""
MONEY_SEEN = "Money amounts are in {currency}."
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
MONEY_HIDDEN = "This person doesn't see money: never mention prices, costs or sales values."


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


def converse(
    db: Session, organization_id: uuid.UUID, currency: str | None, question: str, earlier: list[dict],
    model: str = llm.OLLAMA_MODEL,
) -> Iterator[dict]:
    """Events for the website, in order: {"type": "looking_up"}, {"type": "text"} pieces, then one
    {"type": "done"}. Or a single {"type": "ai_off"} when the model can't be reached."""
    shop = shop_words(db, organization_id)
    earlier = earlier[-EARLIER_TURNS:]
    questions = [question, *(turn["question"] for turn in earlier)]
    money_rule = MONEY_SEEN.format(currency=currency) if currency else MONEY_HIDDEN
    language = reply_language(question)
    messages = [{"role": "system", "content": INSTRUCTIONS.format(
        today=shop_today(db, organization_id), shop_names=shop_names(shop), language=language, money_rule=money_rule
    )}]
    for turn in earlier:
        messages += [{"role": "user", "content": turn["question"]}, {"role": "assistant", "content": turn["answer"]}]
    messages.append({"role": "user", "content": question})

    lookups: list[Lookup] = []
    looked_up: list[object] = []
    text = CheckedText(AllowedNumbers([], questions))
    rechecked = False
    try:
        for round_number in range(ROUNDS):
            can_look_up = round_number < ROUNDS - 1 and len(lookups) < MOST_CALLS
            calls, written = [], ""
            for piece in llm.chat(messages, tool_specs() if can_look_up else None, model):
                calls += piece.get("tool_calls", [])
                written += piece.get("text", "")
                if "text" in piece and (out := text.add(piece["text"])):
                    yield {"type": "text", "text": out}
                if text.wrong:
                    break
            if out := text.finish():
                yield {"type": "text", "text": out}
            if text.wrong and not text.shown and not rechecked and round_number < ROUNDS - 1:
                # Nothing was shown yet: the model gets one more try, told which numbers didn't match.
                rechecked = True
                messages += [{"role": "assistant", "content": written},
                             {"role": "user", "content": RECHECK.format(numbers=", ".join(text.wrong), language=language)}]
                text = CheckedText(text.allowed)
                continue
            if text.wrong or not calls:
                break
            messages.append({"role": "assistant", "content": "", "tool_calls": calls})
            for call in calls[: MOST_CALLS - len(lookups)]:
                function = call.get("function", {})
                name, arguments = function.get("name", ""), function.get("arguments", {})
                lookup = look_up(db, organization_id, currency, shop, name, arguments)
                yield {"type": "looking_up", "tool": name, "filters": lookup.filters}
                lookups.append(lookup)
                content = for_the_model(lookup, currency)
                looked_up.append(json.loads(content))
                messages.append({"role": "tool", "content": content, "tool_name": name})
            text.allowed = AllowedNumbers(looked_up, questions)
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
        "lookups": [_shown(lookup) for lookup in lookups if lookup.answer is not None],
    }


def _shown(lookup: Lookup) -> dict:
    answer = lookup.answer
    return {
        "tool": lookup.tool, "filters": lookup.filters, "key": answer.key, "values": answer.values,
        "sentence": answer.sentence, "numbers": [number.model_dump() for number in answer.numbers],
    }


def as_line(event: dict) -> bytes:
    """One event per line (newline-delimited JSON), read by the website as it arrives."""
    return (json.dumps(event, ensure_ascii=False, default=str) + "\n").encode()

