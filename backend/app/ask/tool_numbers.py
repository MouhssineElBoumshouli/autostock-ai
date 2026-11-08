"""The number check for the online assistant: every number in its answer must come from a tool result
(or from the question, or be a date the shop's data or today gives). Simple roundings count ("about
6 500" for 6 513), and so do the pieces of a date ("3 nov.", "2026"). Anything else is a number the model
made up or computed itself, and the answer is not shown as it is.
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
