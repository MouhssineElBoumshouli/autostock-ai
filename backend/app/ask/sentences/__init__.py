"""The app's own answers, written from the real numbers with hand-written sentences, in English,
French or Arabic (one file each). Always right, and needs no AI: this is the default writer.

Each answer key (app/ask/answers.py) has a function of the same name in each language file, taking
the answer's values and a Shown that writes numbers, dates, money and names for that language.
"""

from collections.abc import Callable
from types import ModuleType

from app.ask.answer_parts import Answer
from app.ask.sentences import ar, en, fr
from app.ask.sentences.shown import Shown

LANGUAGES: dict[str, ModuleType] = {"en": en, "fr": fr, "ar": ar}


def written_answer(answer: Answer, language: str, currency: str | None) -> str:
    """The answer in `language` ("en", "fr" or "ar"). A key without a sentence falls back to English."""
    sentences = LANGUAGES[language]
    if answer.key in sentences.FIXED:
        return sentences.FIXED[answer.key]
    build: Callable | None = getattr(sentences, answer.key, None)
    if build is None:
        return answer.sentence
    return build(answer.values, Shown(language, currency))


def fixed(name: str, language: str) -> str:
    """A sentence that needs no numbers: "refusal", "not_understood", "cannot_answer"."""
    return LANGUAGES[language].FIXED[name]
