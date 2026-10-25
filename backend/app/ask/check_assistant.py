"""Honest score for the "Ask your shop" assistant, per local model, on the 60 open questions of
app/ask/assistant_test_questions.py (written before the assistant, never edited).

The assistant reads each question (rule, follow-up, or model), runs one lookup, and the model writes
the answer from its facts (app/ask/assistant.py). An answer is good when it does what its case says a good answer must contain:
- answerable questions: every needed lookup made with the right filters, every number it must
  mention said (simple rounding allowed), the number check passed, the right language;
- questions to refuse: nothing looked up, a reply with no numbers, the right language.
Also measured: how often the number check stopped an answer, and seconds per answer (and until the
first words show). Follow-ups are asked after their earlier questions, in the same conversation.

Needs the demo shop (python -m app.demo.demo_shop) and Ollama with the models (docker compose --profile ai-gpu up).
Run inside Docker:  docker compose exec api python -m app.ask.check_assistant [model ...] [--misses]
"""

import re
import statistics
import sys
from dataclasses import dataclass, field
from time import perf_counter

from sqlalchemy import select

from app.ai import llm
from app.ask.assistant import converse
from app.ask.assistant_test_questions import ASSISTANT_CASES, AssistantCase
from app.ask.number_check import numbers_written, readings, rounded
from app.ask.question import Question
from app.db import SessionLocal
from app.demo.demo_shop import DEMO_SHOP_NAME
from app.models import Organization, Part
from app.search.part_search import find_parts

MODELS = ("qwen3:4b-instruct", "qwen2.5:3b")
ARABIC = re.compile(r"[؀-ۿ]")
LATIN = re.compile(r"[A-Za-zÀ-ÿ]")
FRENCH = set("le la les des est sont vous nous une pour dans avec sur cette semaine ventes pièces vendu vendues".split())
ENGLISH = set("the is are you we this week sold sales pieces with for and was were".split())
DARIJA = set("dyal kayn kayna had bzaf wach li f m3a 3la chi walo ma daba hna 3ndk 3ndna tba3 bi3".split())


@dataclass
class Result:
    case: AssistantCase
    text: str
    checked: bool
    wrong_numbers: list[str]
    lookups: list[dict]
    seconds: float
    first_words_seconds: float | None
    asked: dict | None = None  # the question as the app understood it, kept for a follow-up
    read_by: str = ""
    misses: list[str] = field(default_factory=list)

    @property
    def good(self) -> bool:
        return not self.misses


def ask_once(db, organization_id, question: str, earlier: dict | None, model: str) -> Result:
    started = perf_counter()
    first_words = None
    done: dict = {}
    previous = Question(earlier["type"], **earlier["filters"]) if earlier else None
    for event in converse(db, organization_id, "MAD", question, previous, model):
        if event["type"] == "text" and first_words is None:
            first_words = perf_counter() - started
        if event["type"] in ("done", "ai_off"):
            done = event
    return Result(None, done.get("text", ""), done.get("checked", False), done.get("wrong_numbers", []),
                  done.get("lookups", []), perf_counter() - started, first_words, done.get("question"), done.get("read_by", ""))


def language_of(text: str) -> str:
    arabic, latin = len(ARABIC.findall(text)), len(LATIN.findall(text))
    if arabic > latin:
        return "arabic_letters"
    words = re.findall(r"[a-zà-ÿ0-9']+", text.lower())
    scores = {name: sum(word in markers for word in words) for name, markers in
              (("en", ENGLISH), ("fr", FRENCH), ("darija", DARIJA))}
    return max(scores, key=scores.get)


def right_language(case: AssistantCase, text: str) -> bool:
    found = language_of(text)
    if case.language in ("ar", "darija"):
        return found == "arabic_letters" or (case.language == "darija" and found == "darija")
    return found == case.language


def part_family_ok(db, organization_id, words: str | None, family: str) -> bool:
    if not words:
        return False
    matches = find_parts(db, organization_id, words).matches
    names = db.scalars(select(Part.name).where(Part.id.in_([part_id for part_id, _ in matches]))).all()
    return bool(names) and all(name.lower().startswith(family.lower()) for name in names)


def need_met(db, organization_id, need, lookups: list[dict]) -> bool:
    for lookup in lookups:
        if lookup["tool"] not in need.tools:
            continue
        filters = lookup["filters"]
        if all(
            part_family_ok(db, organization_id, filters.get("part"), value) if name == "part" else filters.get(name) == value
            for name, value in need.filters.items()
        ):
            return True
    return False


def value_at(lookup: dict, path: str) -> object:
    here: object = lookup["values"]
    for index, step in enumerate(path.split("/")):
        if isinstance(here, dict) and step in here:
            here = here[step]
        elif index == 0:
            return next((number["value"] for number in lookup["numbers"] if number.get("key") == step), None)
        elif isinstance(here, list) and step.isdigit() and int(step) < len(here):
            here = here[int(step)]
        elif isinstance(here, list) and "=" in step:
            key, wanted = step.split("=", 1)
            here = next((item for item in here if isinstance(item, dict) and item.get(key) == wanted), None)
        else:
            return None
    return here


def says_number(text: str, value: object) -> bool:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return False
    targets = {round(shown, 1) for shown in rounded(float(value))}
    return any(round(number, 1) in targets for written in numbers_written(text) for reading in readings(written) for number in reading)


def mention_met(mention: str, lookups: list[dict], text: str) -> bool:
    for option in mention.split("|"):
        tool, path = option.split(":", 1)
        if any(lookup["tool"] == tool and says_number(text, value_at(lookup, path)) for lookup in lookups):
            return True
    return False


def judge(db, organization_id, result: Result) -> None:
    case, misses = result.case, result.misses
    if result.wrong_numbers:
        misses.append(f"number check failed on {result.wrong_numbers}")
    elif not result.text:
        misses.append("no answer")
    if case.refuse:
        if result.lookups:
            misses.append(f"looked up data: {[lookup['tool'] for lookup in result.lookups]}")
        if numbers_written(result.text):
            misses.append("wrote numbers")
    else:
        for need in case.use:
            if not need_met(db, organization_id, need, result.lookups):
                misses.append(f"missing lookup {need.tools} {need.filters}")
        for mention in case.mention:
            if not mention_met(mention, result.lookups, result.text):
                misses.append(f"didn't say {mention}")
    if result.text and not right_language(case, result.text):
        misses.append(f"language: {language_of(result.text)}")


def run_model(db, organization_id, model: str) -> list[Result]:
    ask_once(db, organization_id, "hello", None, model)  # loads the model onto the graphics card first
    results = []
    for case in ASSISTANT_CASES:
        earlier = None
        for question in case.earlier:
            before = ask_once(db, organization_id, question, earlier, model)
            if before.asked and before.asked["type"] != "cannot_answer":
                earlier = before.asked
        result = ask_once(db, organization_id, case.question, earlier, model)
        result.case = case
        judge(db, organization_id, result)
        results.append(result)
        print("." if result.good else "x", end="", flush=True)
    print()
    return results


def percent(part: int, whole: int) -> str:
    return f"{round(100 * part / whole) if whole else 0}%"


def report(model: str, results: list[Result], show_misses: bool) -> None:
    answerable = [r for r in results if not r.case.refuse]
    refusals = [r for r in results if r.case.refuse]
    seconds = [r.seconds for r in results]
    first_words = [r.first_words_seconds for r in results if r.first_words_seconds is not None]
    print(f"\n== {model}")
    print(f"good answers {percent(sum(r.good for r in results), len(results))} "
          f"(answerable {sum(r.good for r in answerable)}/{len(answerable)}, refusals {sum(r.good for r in refusals)}/{len(refusals)})")
    print(f"number check failed {percent(sum(bool(r.wrong_numbers) for r in results), len(results))} "
          f"({sum(bool(r.wrong_numbers) for r in results)}/{len(results)})")
    print(f"seconds per answer: median {statistics.median(seconds):.1f}, mean {statistics.mean(seconds):.1f}, max {max(seconds):.1f}; "
          f"first words median {statistics.median(first_words) if first_words else 0:.1f}")
    for language in ("en", "fr", "ar", "darija"):
        mine = [r for r in results if r.case.language == language]
        print(f"  {language}: {sum(r.good for r in mine)}/{len(mine)}")
    follow_ups = [r for r in results if r.case.earlier]
    print(f"  follow-ups: {sum(r.good for r in follow_ups)}/{len(follow_ups)}")
    readers = {name: sum(r.read_by == name for r in results) for name in ("rule", "follow_up", "model")}
    print(f"  read by: {readers}")
    if show_misses:
        for r in results:
            if not r.good:
                print(f"  x [{r.case.language}] {r.case.question!r}: {'; '.join(r.misses)}\n      -> {r.text[:300]!r}")


def main() -> None:
    show_misses = "--misses" in sys.argv
    wanted = [arg for arg in sys.argv[1:] if not arg.startswith("--")] or list(MODELS)
    with SessionLocal() as db:
        organization_id = db.scalar(select(Organization.id).where(Organization.name == DEMO_SHOP_NAME))
        if organization_id is None:
            sys.exit("No demo shop. Create it first: python -m app.demo.demo_shop")
        for model in wanted:
            if not llm.is_on(model):
                print(f"\n== {model}: not downloaded, skipped")
                continue
            report(model, run_model(db, organization_id, model), show_misses)


if __name__ == "__main__":
    main()
