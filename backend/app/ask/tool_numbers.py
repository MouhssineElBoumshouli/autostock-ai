"""The number check for the online assistant: every number in its answer must come from a tool result
(or from the question, or be a date the shop's data or today gives). Simple roundings count ("about
6 500" for 6 513), and so do the pieces of a date ("3 nov.", "2026"). Anything else is a number the model
made up or computed itself, and the answer is not shown as it is.

A change's number is allowed without its sign ("down 9 %"), so the direction is checked apart: when every
comparison the tools made went the same way, an answer that only says the opposite way is wrong.
"""

import re
from datetime import date

from app.ask.number_check import numbers_written, readings, rounded

ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
ALWAYS = {0.0, 1.0}  # "one part", "no sale": too common to block


def allowed_numbers(results: list[object], texts: list[str], days: list[date]) -> set[float]:
    """Every number in the tool results (and their roundings), the numbers typed in `texts` (the question)
    and the pieces of every date in them or in `days` (today, the last sale)."""
    found: set[float] = set(ALWAYS)
    for result in results:
        _collect(result, found)
    for text in texts:
        for written in numbers_written(text):
            for reading in readings(written):
                found.update(reading)
    for day in days:
        found.update(_date_pieces(day))
    return {shown for value in found for shown in rounded(value)}


def _collect(value: object, found: set[float]) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, int | float):
        found.add(float(value))
        found.add(abs(float(value)))  # a change is said with a word for its direction: "down 9 %"
    elif isinstance(value, str):
        for year, month, day in ISO_DATE.findall(value):
            found.update(_date_pieces(date(int(year), int(month), int(day))))
        for written in numbers_written(ISO_DATE.sub(" ", value)):  # "Sold 29 in 7 days", "Mercedes 190"
            for reading in readings(written):
                found.update(reading)
    elif isinstance(value, dict):
        for item in value.values():
            _collect(item, found)
    elif isinstance(value, list | tuple):
        for item in value:
            _collect(item, found)


def _date_pieces(day: date) -> set[float]:
    return {float(day.year), float(day.month), float(day.day)}


def unknown_numbers(text: str, allowed: set[float]) -> list[str]:
    """The numbers written in `text` that no tool result gives."""
    return [written for written in numbers_written(text)
            if not any(all(_close_to(number, allowed) for number in reading) for reading in readings(written))]


def _close_to(number: float, allowed: set[float]) -> bool:
    return number in allowed or any(abs(number - value) < 0.006 for value in allowed)


UP_WORDS = re.compile(r"\b(up|rose|risen|increased?|increases|grew|growth|higher|more than|hausse|augment\w*|progress\w*|"
                      r"plus que|zad\w*|ارتفع\w*|زاد\w*|زياده|ارتفاع)\b", re.IGNORECASE)
DOWN_WORDS = re.compile(r"\b(down|fell|fallen|dropp?ed|drop|decreased?|decline\w*|lower|less|fewer|baiss\w*|diminu\w*|recul\w*|"
                        r"moins|n9as\w*|انخفض\w*|انخفاض|تراجع\w*|نقص\w*|قل)\b", re.IGNORECASE)

LAST_YEAR_WORDS = re.compile(r"last year|year before|an dernier|année dernière|année précédente|السنه الماضيه|العام الماضي|3am li fat",
                             re.IGNORECASE)


def wrong_direction(text: str, results: list[object]) -> str | None:
    """"down" when the comparisons asked for went down but the answer only says up (or the reverse). An answer
    that talks about last year may rightly say the other way for it: then only an answer with no direction word
    for the main change could be judged, so it is left alone."""
    if LAST_YEAR_WORDS.search(text):
        return None
    directions = {result["compared_with"].get("direction") for result in results
                  if isinstance(result, dict) and isinstance(result.get("compared_with"), dict)}
    directions |= {result["direction"] for result in results if isinstance(result, dict) and result.get("direction")}  # why_sales
    directions.discard("same")
    if len(directions) != 1:
        return None
    went = directions.pop()
    says_up, says_down = bool(UP_WORDS.search(text)), bool(DOWN_WORDS.search(text))
    if went == "down" and says_up and not says_down:
        return "down"
    if went == "up" and says_down and not says_up:
        return "up"
    return None


def missing_counts(text: str, results: list[object]) -> str | None:
    """A "will I run out" answer must give how many part-branches are at risk and how many are already at zero
    (the owner's trial: "plusieurs références" without the numbers). Returns the counts left out, or None."""
    written = {number for item in numbers_written(text) for reading in readings(item) for number in reading}
    for result in results:
        if isinstance(result, dict) and "order_first_from" in result and result.get("at_risk"):
            needed = [result["at_risk"]] + ([result["out_now"]] if result.get("out_now") else [])
            left_out = [str(count) for count in needed if float(count) not in written]
            if left_out:
                return ", ".join(left_out)
    return None
