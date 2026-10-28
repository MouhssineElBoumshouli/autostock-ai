"""Finding the numbers in a text, however they are written: digits (1,234 · 1 234 · 1.234,5),
Arabic digits, or words ("twenty-five", "vingt", "عشرون"). Used to block any number the writer types
itself (app/ask/fact_check.py) and to score answers (app/ask/check_assistant.py).
"""

import re

from app.ask.words import words_of

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,")
# 1234 · 1,234 · 1 234 · 1.234,5 · 12.5 — grouped thousands with a comma, dot or space.
NUMBER = re.compile(r"\d+(?:[   ,.]\d{3}(?!\d))*(?:[.,]\d+)?")
LIST_MARKER = re.compile(r"^(\s*)\d{1,2}[.)](?=\s)", re.MULTILINE)  # "1. " starting a line is a list, not a number
# Darija written in Latin letters uses single digits as letters: "3tini", "m3a", "ch7al", "9aren".
# A single 2, 3, 5, 7, 8 or 9 inside a word of letters is a letter, not a number.
DARIJA_LETTER = re.compile(r"(?<!\d)(?:(?<=[^\W\d_])[235789](?=[^\W\d_])|\b[235789](?=[^\W\d_]{2,})|(?<=[^\W\d_]{2})[235789]\b)(?!\d)")

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
    text = DARIJA_LETTER.sub("", LIST_MARKER.sub(r"\1", text.translate(ARABIC_DIGITS)))
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


def rounded(value: float) -> set[float]:
    """The number and its simple roundings: whole, one decimal, 2 or 3 significant digits ("about 1,200")."""
    shown = {value, round(value), round(value, 1)}
    for digits in (2, 3):
        size = len(str(int(abs(value))))
        if size > digits:
            shown.add(round(value, digits - size))
    return shown
