"""Dates in the online assistant's answers, written in words: "2026-10-01" becomes "1er octobre" (French),
"October 1" (English), "1 أكتوبر" (Arabic); the year only when it isn't the current one. Done by the app after
the number check, so the model's dates are always shown the shop's way."""

import re
from datetime import date

MONTHS = {
    "fr": "janvier février mars avril mai juin juillet août septembre octobre novembre décembre".split(),
    "en": "January February March April May June July August September October November December".split(),
    "ar": "يناير فبراير مارس أبريل ماي يونيو يوليوز غشت شتنبر أكتوبر نونبر دجنبر".split(),
}
DASH = "[-‐‑–/.]"
YEAR_FIRST = re.compile(rf"\b(\d{{4}}){DASH}(\d{{1,2}}){DASH}(\d{{1,2}})\b")
DAY_FIRST = re.compile(rf"\b(\d{{1,2}}){DASH}(\d{{1,2}}){DASH}(\d{{4}})\b")


def in_words(text: str, language: str, today: date) -> str:
    def say(year: int, month: int, day: int) -> str | None:
        try:
            date(year, month, day)
        except ValueError:
            return None
        name = MONTHS[language][month - 1]
        number = "1er" if language == "fr" and day == 1 else str(day)
        words = f"{name} {day}" if language == "en" else f"{number} {name}"
        return words if year == today.year else f"{words}{',' if language == 'en' else ''} {year}"

    text = YEAR_FIRST.sub(lambda m: say(int(m[1]), int(m[2]), int(m[3])) or m[0], text)
    return DAY_FIRST.sub(lambda m: say(int(m[3]), int(m[2]), int(m[1])) or m[0], text)
