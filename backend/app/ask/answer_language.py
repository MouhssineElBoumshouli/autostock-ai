"""Which language a written answer is in: Arabic letters, or French or English by their most common
words. Names (branches, parts) are left out first, since they are written the same in every language.

Kept apart from the scoring script's own check (app/ask/check_assistant.py) on purpose: what measures
the answers must not be the same code that produced them.
"""

import re

ARABIC_LETTER = re.compile(r"[؀-ۿ]")
LATIN_LETTER = re.compile(r"[A-Za-zÀ-ÿ]")
WORD = re.compile(r"[a-zà-ÿ']+")
FRENCH = set("""le la les des du de est sont une un pour dans avec sur cette ce ces vendu vendues vendus pièces
    semaine mois et à par il elle nous vous en au aux qui que pas plus moins été ont aucune aucun période
    précédente dernier dernière alertes commander stock""".split())
ENGLISH = set("""the is are was were this that these those sold pieces week month and in of to for with by has
    have had than more less on at from period before last alerts order no none""".split())
CODES = {"English": "en", "French": "fr"}  # every other answer is written in Arabic letters


def written_in(text: str, names: list[str]) -> str | None:
    """"ar", "fr" or "en"; None when the text is too short to tell (only names and numbers)."""
    for name in sorted(names, key=len, reverse=True):
        text = text.replace(name, " ")
    arabic, latin = len(ARABIC_LETTER.findall(text)), len(LATIN_LETTER.findall(text))
    if arabic > latin:
        return "ar"
    words = WORD.findall(text.lower())
    french, english = sum(word in FRENCH for word in words), sum(word in ENGLISH for word in words)
    if french == english:
        return "ar" if arabic else None
    return "fr" if french > english else "en"


def in_language(text: str, language: str, names: list[str]) -> bool:
    """`language` as the writer was told it ("French", "Arabic", ...)."""
    found = written_in(text, names)
    return found is None or found == CODES.get(language, "ar")
