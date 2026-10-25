"""Checks that every number the model wrote comes from the shop's real data.

Allowed: the numbers in what the app looked up (tool results, their words included: "BP-1042",
"2026-10-21"), the numbers in the person's own questions, and what simple arithmetic on the looked-up
facts gives: rounding, a sum or a difference of two facts, one as a percentage of the other, or the
percentage change between them. Anything else fails, and the app shows its own safe answer instead.
"""

import re
from itertools import permutations

from app.ask.words import words_of

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,")
# 1234 · 1,234 · 1 234 · 1.234,5 · 12.5 — grouped thousands with a comma, dot or space.
NUMBER = re.compile(r"\d+(?:[   ,.]\d{3}(?!\d))*(?:[.,]\d+)?")
LIST_MARKER = re.compile(r"^(\s*)\d{1,2}[.)](?=\s)", re.MULTILINE)  # "1. " starting a line is a list, not a number
ALWAYS_ALLOWED = (0,)
MOST_PAIRED = 200  # enough for any one answer, and keeps the check instant

# Numbers written as words are checked too. Words that also mean something else are left out:
# "one"/"un"/"واحد" (also "a", "this one"), "neuf" (also "new"), "cent" (also in "pour cent").
NUMBER_WORDS = {
    **dict(zip("two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
               "seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand dozen".split(),
               [*range(2, 21), 30, 40, 50, 60, 70, 80, 90, 100, 1000, 12])),
    **dict(zip("deux trois quatre cinq six sept huit dix onze douze treize quatorze quinze seize vingt trente quarante "
               "cinquante soixante mille".split(), [2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 20, 30, 40, 50, 60, 1000])),
    **dict(zip("jouj tlata rb3a khamsa stta sb3a tmnya ts3od 3achra 3chrin".split(), [2, 3, 4, 5, 6, 7, 8, 9, 10, 20])),
    **{word: value for value, spellings in {
        2: "اثنان اثنين اثنتان اثنتين جوج", 3: "ثلاثه ثلاث", 4: "اربعه اربع", 5: "خمسه خمس", 6: "سته ست", 7: "سبعه سبع",
        8: "ثمانيه ثماني", 9: "تسعه تسع", 10: "عشره عشر", 20: "عشرون عشرين", 30: "ثلاثون ثلاثين", 40: "اربعون اربعين",
        50: "خمسون خمسين", 60: "ستون ستين", 70: "سبعون سبعين", 80: "ثمانون ثمانين", 90: "تسعون تسعين",
        100: "مئه مائه", 200: "مئتان مائتان مئتين", 1000: "الف", 2000: "الفان الفين",
    }.items() for word in spellings.split()},
}


def numbers_written(text: str) -> list[str]:
    text = LIST_MARKER.sub(r"\1", text.translate(ARABIC_DIGITS))
    return NUMBER.findall(text) + numbers_in_words(text)


def _word_value(word: str) -> int | None:
    if word in NUMBER_WORDS:
        return NUMBER_WORDS[word]
    if word.startswith("و") and word[1:] in NUMBER_WORDS:  # Arabic "and" is glued: "خمسه وعشرون"
        return NUMBER_WORDS[word[1:]]
    return None


def numbers_in_words(text: str) -> list[str]:
    """"twenty-five" -> "25", "quatre-vingt" -> "80", "خمسة وعشرون" -> "25"."""
    found, total, previous = [], None, None
    for word in [*words_of(text), ""]:
        value = _word_value(word)
        if value is None:
            if word in ("and", "et") and total is not None:
                continue
            if total is not None:
                found.append(str(total))
            total = previous = None
            continue
        if total is None:
            total = value
        elif value in (100, 1000):
            total *= value
        elif previous == 4 and value == 20:
            total += 76  # quatre-vingt
        else:
            total += value
        previous = value
    return found


def readings(written: str) -> list[list[float]]:
    """Every way a written number can be read; one reading is a list of numbers that must all be allowed.
    "1,234.5", "1.234,5" and "1 234" are each one number; "3 120" may also be 3 and 120."""
    compact = re.sub(r"[   ]", "", written)
    ways = []
    for thousands, decimal in ((",", "."), (".", ",")):
        try:
            ways.append([float(compact.replace(thousands, "").replace(decimal, "."))])
        except ValueError:
            pass
    pieces = [float(piece) for piece in re.split(r"[   ,.]", written) if piece]
    if len(pieces) > 1:
        ways.append(pieces)
    return ways


def _key(value: float) -> float:
    return round(value, 1)


def rounded(value: float) -> set[float]:
    """The number and its simple roundings: whole, one decimal, 2 or 3 significant digits ("about 1,200")."""
    shown = {value, round(value), round(value, 1)}
    for digits in (2, 3):
        size = len(str(int(abs(value))))
        if size > digits:
            shown.add(round(value, digits - size))
    return shown


def _collect(source: object, facts: list[float], in_words: list[float]) -> None:
    """Numbers that are facts (counts, pieces, money, percentages) go to `facts`; numbers inside
    words (dates, part numbers, sentences) and list lengths go to `in_words`."""
    if isinstance(source, bool) or source is None:
        return
    if isinstance(source, int | float):
        facts.append(float(source))
    elif isinstance(source, str):
        for written in numbers_written(source):
            for reading in readings(written):
                in_words.extend(reading)
    elif isinstance(source, dict):
        for value in source.values():
            _collect(value, facts, in_words)
    elif isinstance(source, list | tuple):
        in_words.append(float(len(source)))  # "the top 5"
        for value in source:
            _collect(value, facts, in_words)


class AllowedNumbers:
    """Arithmetic is only allowed on facts: otherwise the pieces of a date (2026, 10, 21) could add
    up to almost any small number, and an invented one would pass."""

    def __init__(self, looked_up: list[object], questions: list[str]):
        facts: list[float] = []
        in_words: list[float] = []
        for source in looked_up:
            _collect(source, facts, in_words)
        for question in questions:  # the person's own numbers ("set it to 50")
            _collect(question, in_words, in_words)
        facts = list(dict.fromkeys(facts))
        allowed = set(ALWAYS_ALLOWED) | set(in_words)
        for value in facts:
            allowed |= rounded(value)
        for first, second in permutations(facts[:MOST_PAIRED], 2):
            derived = [first + second, abs(first - second)]
            if second:
                derived += [100 * first / second, abs(100 * (first - second) / second), first / second]
            for value in derived:
                allowed |= rounded(value)
        self._keys = {_key(value) for value in allowed}

    def allows(self, value: float) -> bool:
        return _key(value) in self._keys

    def wrong_numbers(self, text: str) -> list[str]:
        """The numbers in `text` that no reading makes allowed."""
        return [
            written for written in numbers_written(text)
            if not any(all(self.allows(value) for value in reading) for reading in readings(written))
        ]
