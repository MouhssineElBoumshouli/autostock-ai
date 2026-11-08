"""Honest score for the online assistant (Groq + read-only tools) on the 50 questions of
app/ask/real_shop_questions.py (written before the assistant, never edited), and the owner's 10 questions.

Needs a copy of the owner's trial shop in the database (its numbers are what the 50 questions expect) and
GROQ_API_KEY. "Today" is pinned to 2026-11-08, the day the questions were written.

For each question it records the answer, the lookups, seconds and tokens, and checks:
- right numbers: every number the case's `truth` asks for is said (simple rounding allowed). The truth is
  computed here with plain SQL, never with the assistant's tools.
- wrong numbers: a number for the asked thing that differs from the truth, or a number no tool gave. Both
  must be 0. A case is flagged "to read" when the answer's numbers don't contain the truth, so a person
  can tell a wrong number from a missing one.
- refusals: no number at all (a refused action or a question the data can't answer).
- language: the question's.
- natural: at most 3 sentences and 80 words, no markdown or list (a person then reads them all, see the doc).
Results are saved after each answer (resumable: Groq's free tier allows about 8,000 tokens a minute and
200,000 a day), in check_real_assistant_<model>.json.

Run inside Docker:  docker compose exec api python -m app.ask.check_real_assistant [model] [--owner] [--most=N]
--most=N: ask Groq at most N questions (follow-ups' earlier questions count), so the shop keeps some of the day's allowance.
"""

import json
import re
import statistics
import sys
import time
from datetime import date
from pathlib import Path

from sqlalchemy import text

from app.ai import groq
from app.ask.number_check import numbers_written, readings, rounded
from app.ask.online_assistant import AnswerRejected, EarlierTurn, answer
from app.ask.real_shop_questions import OWNER_QUESTIONS, REAL_CASES, RealCase
from app.ask.tool_numbers import allowed_numbers, unknown_numbers
from app.db import SessionLocal
from app.models import Organization

TODAY = date(2026, 11, 8)
APP_LANGUAGE = "fr"  # the owner's shop language
TOKENS_PER_MINUTE = 7000  # stays under Groq's 8,000 a minute
RESULTS = Path(__file__).resolve().parent.parent.parent / "check_results"
ARABIC = re.compile(r"[؀-ۿ]")
FRENCH = set("le la les des est sont une pour dans avec sur cette ces pièces vendu vendues ventes stock il reste aucun "
             "aucune nous vous du au aux mois semaine depuis".split())
ENGLISH = set("the is are you we this week sold sales pieces with for and was were in of no our has have".split())
DARIJA = set("dyal kayn kayna had bzaf wach li f m3a 3la chi walo ma daba hna 3ndk 3ndna tba3 bi3 bi3na".split())


# The truth, with plain SQL (never the assistant's tools)

TYPE = "split_part(p.name, ' - ', 1)"
CAR = "split_part(p.name, ' - ', 2)"


def _part_where(filters: dict) -> tuple[str, dict]:
    where, values = ["p.organization_id = :org"], {}
    if filters.get("type"):
        where.append(f"{TYPE} ILIKE :type")
        values["type"] = filters["type"] + "%"
    if filters.get("car"):
        where.append(f"{CAR} = :car")
        values["car"] = filters["car"]
    if filters.get("brand"):
        where.append("p.brand = :brand")
        values["brand"] = filters["brand"]
    return " AND ".join(where), values


def _branch(filters: dict, column: str) -> tuple[str, dict]:
    if not filters.get("branch"):
        return "", {}
    return f" AND {column} = (SELECT id FROM branches WHERE organization_id = :org AND name = :branch)", {"branch": filters["branch"]}


def truth(db, organization_id, kind: str, filters: dict) -> list[float]:
    """The number(s) the answer must say; several are alternatives (any one counts)."""
    where, values = _part_where(filters)
    branch, branch_values = _branch(filters, "x.branch_id")
    values = {"org": organization_id, **values, **branch_values, "first": filters.get("from"), "last": filters.get("to")}

    def one(sql: str) -> float:
        return float(db.execute(text(sql), values).scalar() or 0)

    if kind == "stock":
        return [one(f"SELECT sum(x.quantity) FROM stock_levels x JOIN parts p ON p.id = x.part_id WHERE {where}{branch}")]
    if kind == "sales":
        return [one(f"SELECT sum(x.quantity) FROM sale_lines x JOIN parts p ON p.id = x.part_id WHERE {where}{branch} "
                    "AND x.sold_on BETWEEN :first AND :last")]
    if kind == "last_sale_day":
        return [float(db.execute(text("SELECT max(sold_on) FROM sale_lines WHERE organization_id = :org"), values).scalar().day)]
    if kind in ("top_part", "top_type", "top_branch"):
        group = {"top_part": ["p.id", "p.name"], "top_type": [TYPE], "top_branch": ["x.branch_id"]}[kind]
        return [one(f"SELECT sum(x.quantity) FROM sale_lines x JOIN parts p ON p.id = x.part_id WHERE {where}{branch} "
                    f"AND x.sold_on BETWEEN :first AND :last GROUP BY {by} ORDER BY 1 DESC LIMIT 1") for by in group]
    if kind == "open_alerts":
        return [one("SELECT count(*) FROM alerts WHERE organization_id = :org AND status = 'open'")]
    if kind == "stock_out_days":
        return [one(f"SELECT sum(least(x.last_day, :last) - greatest(x.first_day, :first) + 1) FROM stock_outs x "
                    f"JOIN parts p ON p.id = x.part_id WHERE {where}{branch} AND x.first_day <= :last AND x.last_day >= :first")]
    if kind == "forecast":
        values["days"] = filters["days"]
        return [round(one(f"SELECT sum(x.quantity) FROM forecasts x JOIN parts p ON p.id = x.part_id WHERE {where}{branch} "
                          "AND x.horizon_days = :days"))]
    if kind == "supplier_days":
        values["name"] = filters["name"]
        return [one("SELECT delivery_days FROM suppliers WHERE organization_id = :org AND name = :name")]
    if kind in ("dead_parts", "dead_value"):
        values["days"] = filters["days"]
        measure = "count(*)" if kind == "dead_parts" else "round(sum(s.quantity * coalesce(p.unit_cost, 0)) / 100.0)"
        return [one(f"""SELECT {measure} FROM parts p JOIN (SELECT part_id, sum(quantity) AS quantity FROM stock_levels
                        WHERE organization_id = :org GROUP BY part_id) s ON s.part_id = p.id
                        WHERE p.organization_id = :org AND p.is_active AND s.quantity > 0 AND NOT EXISTS (
                          SELECT 1 FROM sale_lines l WHERE l.organization_id = :org AND l.part_id = p.id
                          AND l.sold_on > (SELECT max(sold_on) FROM sale_lines WHERE organization_id = :org) - :days)""")]
    if kind == "margin_percent":
        return [one(f"SELECT round(avg((p.sale_price - p.unit_cost) * 100.0 / p.sale_price)) FROM parts p WHERE {where}")]
    if kind == "sale_price":
        return [float(price) / 100 for price in db.execute(text(f"SELECT DISTINCT p.sale_price FROM parts p WHERE {where}"), values).scalars()]
    raise ValueError(kind)


# Judging one answer

def said(text: str) -> set[float]:
    return {number for written in numbers_written(text) for reading in readings(written) for number in reading}


def mentions(text: str, wanted: list[float]) -> bool:
    found = said(text)
    if any(value == 0 for value in wanted) and re.search(r"\b(aucun|aucune|pas de|no |none|zéro|zero|0)\b", text.lower()):
        return True
    return any(found & rounded(value) or any(abs(number - value) <= 0.5 for number in found) for value in wanted)


def language_of(text: str) -> str:
    if len(ARABIC.findall(text)) > len(re.findall(r"[A-Za-zÀ-ÿ]", text)):
        return "ar"
    words = re.findall(r"[a-zà-ÿ0-9']+", text.lower())
    scores = {name: sum(word in marks for word in words) for name, marks in (("en", ENGLISH), ("fr", FRENCH), ("darija", DARIJA))}
    return max(scores, key=scores.get)


def right_language(case_language: str, text: str) -> bool:
    found = language_of(text)
    if case_language in ("ar", "darija"):
        return found == "ar" or (case_language == "darija" and found == "darija")
    return found == case_language


def natural(text: str) -> bool:
    sentences = [part for part in re.split(r"(?<=[.!?؟])\s+", text.strip()) if part]
    return len(sentences) <= 3 and len(text.split()) <= 80 and not re.search(r"(^|\n)\s*([-*•]|\d+[.)])\s|\*\*|\|", text)


def judged(db, organization_id, case: RealCase, result: dict, earlier_facts: list) -> dict:
    checks: dict = {}
    reply = result.get("text", "")
    if result.get("fell_back"):
        checks["fell_back"] = result["fell_back"]
    if case.refuse:
        checks["right"] = bool(reply) and not said(reply) - {0.0}
    elif case.truth:
        wanted = [truth(db, organization_id, kind, filters) for kind, filters in case.truth]
        checks["truth"] = wanted
        checks["right"] = bool(reply) and all(mentions(reply, values) for values in wanted)
        checks["to_read"] = not checks["right"]
    else:
        checks["right"] = None  # read by a person (docs/ask-real-assistant.md)
    allowed = allowed_numbers(result.get("facts", []) + earlier_facts, [case.question, *case.earlier], [TODAY, date(2026, 11, 3)])
    checks["not_from_tools"] = unknown_numbers(reply, allowed) if reply else []
    checks["language"] = right_language(case.language, reply) if reply else False
    checks["natural"] = natural(reply) if reply else False
    return checks


# Asking

class OutOfAnswers(Exception):
    """--most reached, or Groq's daily allowance used up: stop asking."""


class Pace:
    """Waits so the questions stay under Groq's tokens-a-minute limit, and counts the questions asked (--most)."""

    def __init__(self, most: int | None = None):
        self.spent: list[tuple[float, int]] = []
        self.left = most

    def wait(self, next_tokens: int = 3500) -> None:
        while True:
            now = time.time()
            self.spent = [(when, tokens) for when, tokens in self.spent if now - when < 60]
            if sum(tokens for _, tokens in self.spent) + next_tokens <= TOKENS_PER_MINUTE:
                return
            time.sleep(2)

    def add(self, tokens: int) -> None:
        self.spent.append((time.time(), tokens))


def ask(organization_id, question: str, earlier: list[EarlierTurn], model: str, pace: Pace) -> dict:
    if pace.left is not None:
        if pace.left <= 0:
            raise OutOfAnswers
        pace.left -= 1
    pace.wait()
    started = time.perf_counter()
    with SessionLocal() as db:
        try:
            for event in answer(db, organization_id, "MAD", question, earlier, APP_LANGUAGE, TODAY, model):
                if event["type"] == "done":
                    pace.add(event["tokens"])
                    return {**event, "wall_seconds": round(time.perf_counter() - started, 2)}
        except groq.GroqFailed as failure:
            pace.add(3000)
            return {"text": "", "fell_back": failure.reason, "wall_seconds": round(time.perf_counter() - started, 2)}
        except AnswerRejected as rejected:
            pace.add(5000)
            return {"text": "", "fell_back": f"unchecked: {rejected.numbers}", "wall_seconds": round(time.perf_counter() - started, 2)}
    return {"text": "", "fell_back": "no answer"}


def turn(question: str, result: dict) -> EarlierTurn:
    return EarlierTurn(question, result.get("text", ""), result.get("facts", []))


def run_cases(organization_id, model: str, path: Path, pace: Pace) -> list[dict]:
    saved = json.loads(path.read_text()) if path.exists() else {}
    for index, case in enumerate(REAL_CASES):
        key = str(index)
        if key in saved and saved[key]["result"].get("fell_back") not in ("daily_limit", "busy", "offline"):
            continue
        if pace.left is not None and pace.left < 1 + len(case.earlier):
            print(f"\n--most reached: stopped before question {index + 1}.")
            break
        earlier = []
        for question in case.earlier:
            earlier.append(turn(question, ask(organization_id, question, earlier, model, pace)))
        result = ask(organization_id, case.question, earlier, model, pace)
        if result.get("fell_back") == "daily_limit":
            print("\nGroq's daily allowance is used up: run again later, it goes on from here.")
            break
        with SessionLocal() as db:
            facts = [fact for earlier_turn in earlier for fact in earlier_turn.facts]
            saved[key] = {"case": case.__dict__, "result": result, "checks": judged(db, organization_id, case, result, facts)}
        path.write_text(json.dumps(saved, ensure_ascii=False, indent=1, default=str))
        print("." if saved[key]["checks"]["right"] else "?" if saved[key]["checks"]["right"] is None else "x", end="", flush=True)
    print()
    return [saved[key] for key in sorted(saved, key=int)]


def run_owner(organization_id, model: str, path: Path, pace: Pace) -> None:
    earlier, rows = [], []
    for question in OWNER_QUESTIONS:
        follow_up = question.lower().startswith("et ")
        try:
            result = ask(organization_id, question, earlier if follow_up else [], model, pace)
        except OutOfAnswers:
            print("\n--most reached.")
            break
        if result.get("fell_back") == "daily_limit":
            print("\nGroq's daily allowance is used up.")
            break
        earlier = [turn(question, result)]
        rows.append({"question": question, "result": result})
        print(".", end="", flush=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str))
    print()


def report(model: str, rows: list[dict]) -> None:
    done = [row for row in rows if not row["checks"].get("fell_back")]
    scored = [row for row in done if row["checks"]["right"] is not None]
    seconds = [row["result"]["wall_seconds"] for row in done]
    tokens = [row["result"]["tokens"] for row in done]
    print(f"\n== {model}: {len(rows)} questions, {len(rows) - len(done)} fell back to the app")
    print(f"right (checked against the truth or refused properly): {sum(row['checks']['right'] for row in scored)}/{len(scored)}; "
          f"read by a person: {len(done) - len(scored)}")
    print(f"numbers no tool gave: {sum(bool(row['checks']['not_from_tools']) for row in done)}; "
          f"answers to read for a wrong number: {sum(bool(row['checks'].get('to_read')) for row in done)}")
    print(f"right language {sum(row['checks']['language'] for row in done)}/{len(done)}; "
          f"natural length/format {sum(row['checks']['natural'] for row in done)}/{len(done)}")
    if done:
        print(f"seconds: median {statistics.median(seconds):.1f}, max {max(seconds):.1f}; "
              f"tokens: median {statistics.median(tokens):.0f}, mean {statistics.mean(tokens):.0f}, max {max(tokens)}")
    for row in rows:
        mark = {True: "ok", False: "XX", None: "??"}[row["checks"]["right"]]
        print(f"{mark} [{row['case']['language']}/{row['case']['kind']}] {row['case']['question']}\n     -> {row['result'].get('text') or row['checks'].get('fell_back')}"
              + (f"\n     truth {row['checks']['truth']}" if row["checks"].get("to_read") else "")
              + (f"\n     NOT FROM TOOLS {row['checks']['not_from_tools']}" if row["checks"]["not_from_tools"] else ""))


def main() -> None:
    models = [arg for arg in sys.argv[1:] if not arg.startswith("--")] or [groq.GROQ_MODEL]
    RESULTS.mkdir(exist_ok=True)
    with SessionLocal() as db:
        organization_id = db.query(Organization.id).filter(Organization.name == "Pièces Auto Al Amal").scalar()
    if organization_id is None:
        sys.exit("Needs a copy of the owner's trial shop (Pièces Auto Al Amal).")
    most = next((int(arg.split("=")[1]) for arg in sys.argv if arg.startswith("--most=")), None)
    for model in models:
        name = model.replace("/", "_")
        pace = Pace(most)
        if "--owner" in sys.argv:
            run_owner(organization_id, model, RESULTS / f"owner_questions_{name}.json", pace)
        else:
            report(model, run_cases(organization_id, model, RESULTS / f"real_questions_{name}.json", pace))
        print(f"Groq questions asked: {most - pace.left}" if most is not None else "")


if __name__ == "__main__":
    main()
