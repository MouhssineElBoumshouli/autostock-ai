"""Which language to answer in: the question's own. Arabic letters or Darija (in either alphabet) get
Arabic; otherwise French or English by their common words. A question with too few words to tell
("stock ?") gets the person's app language.
"""

import re

from app.ask.words import words_of

ARABIC_LETTER = re.compile(r"[؀-ۿ]")
DARIJA_SPELLING = re.compile(r"\b[a-z]*[379][a-z]+")  # "3lach", "m9arna", "ch7al": Darija written with digits
DARIJA_WORDS = set(words_of(
    "dyal dial kayn kayna chno chnou ach wach 3lach kifach ch7al chhal bzaf daba lyoum simana khassni khassna "
    "3tini bghit m9arna nkhaf mno kolchi kaytba3ch w f "  # not "ma": French has it too
    "واش شحال ديال كيداير علاش كيفاش دابا بزاف هاد السيمانة خاصني عطيني بغيت باقي"
))
FRENCH_WORDS = set(words_of(
    "le la les des du est sont quoi quel quelle quelles combien pourquoi comment nous vous il reste ventes "
    "agence semaine mois neuf donne moi tout toutes tous sur et une chez de qu ce cette ces mon ma mes au aux pour "
    "dernier dernière vend vendu commande commander rupture ruptures alertes pièces aujourd hui hier"
))
# Words both languages share ("on", "stock", "alerte"...) are in neither list.
ENGLISH_WORDS = set(words_of(
    "the is are what whats which why how many much do does did we our you sell sold sales this last week month "
    "and in of to for me tell about any will should order left running out going today yesterday have has "
    "all who our best give show list set change add delete remove please can parts part sell selling"
))


def is_darija(question: str) -> bool:
    return bool(set(words_of(question)) & DARIJA_WORDS) or bool(DARIJA_SPELLING.search(question.lower()))


def reply_language(question: str, app_language: str) -> str:
    """"en", "fr" or "ar"."""
    if ARABIC_LETTER.search(question) or is_darija(question):
        return "ar"
    words = words_of(question)
    french = sum(word in FRENCH_WORDS for word in words)
    english = sum(word in ENGLISH_WORDS for word in words)
    if french == english:
        return app_language
    return "fr" if french > english else "en"
