"""Honest score for "Ask your shop" on both labeled question sets (app/ask/blind_test_questions.py
and app/ask/blind_test_counter_questions.py), for every way of reading a question:
- rule: the keyword rule alone;
- model: a local model alone (the rule only when the model's answer is rejected);
- hybrid: the rule, and the model only when the rule is unsure.

Each answer is one of:
- right: right question type AND every filter right (part compared without little words,
  accents or case);
- safe: "not sure, did you mean..." or "I can't answer that yet" — no answer, but no harm;
- wrong: it answered a different question than the one asked (the worst outcome).

Needs Ollama for the model columns (docker compose --profile ai up, then
docker compose exec ollama ollama pull qwen2.5:3b for the larger model).

Run inside Docker:  docker compose exec api python -m app.ask.check_questions [--misses]
"""

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from time import perf_counter

from app.ai import llm
from app.ask.blind_test_counter_questions import BLIND_COUNTER_QUESTIONS
from app.ask.blind_test_questions import BLIND_QUESTIONS, BlindQuestion
from app.ask.keyword_rule import read_with_rule
from app.ask.model_reader import read_with_model
from app.ask.question import NOT_SURE, Question, ShopWords
from app.ask.words import content_key, vocabulary
from app.demo.demo_shop import BRANCHES, CARS, FAMILIES
from app.search.default_synonyms import DEFAULT_SYNONYMS

MODELS = ("qwen2.5:1.5b", "qwen2.5:3b")
LANGUAGES = ("en", "fr", "ar", "darija")
SETS = {"First set": BLIND_QUESTIONS, "Counter set": BLIND_COUNTER_QUESTIONS}

DEMO_SHOP = ShopWords(
    categories=tuple(sorted({family[1] for family in FAMILIES})),
    branches=tuple(sorted(BRANCHES)),
    part_words=vocabulary([*(family[0] for family in FAMILIES), *(b for f in FAMILIES for b in f[2]), *CARS,
                           *(word for group in DEFAULT_SYNONYMS for word in group)]),
)


def is_right(question: Question, expected_type: str, expected: dict[str, str]) -> bool:
    if question.type != expected_type:
        return False
    if any(getattr(question, name) != expected.get(name) for name in ("category", "branch", "period")):
        return False
    return content_key(question.part or "") == content_key(expected.get("part", ""))


def outcome(question: Question, expected_type: str, expected: dict[str, str]) -> str:
    if is_right(question, expected_type, expected):
        return "right"
    if question.type in (NOT_SURE, "cannot_answer"):
        return "safe"
    return "wrong"


@dataclass
class Score:
    outcomes: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    seconds: list[float] = field(default_factory=list)

    def add(self, language: str, result: str, seconds: float) -> None:
        self.outcomes[language].append(result)
        self.outcomes["all"].append(result)
        self.seconds.append(seconds)

    def percent(self, key: str, result: str = "right") -> str:
        found = self.outcomes[key]
        return f"{100 * found.count(result) / len(found):.0f}%" if found else "-"


def score_set(questions: list[BlindQuestion], models: list[str], show_misses: bool) -> dict[str, Score]:
    scores: dict[str, Score] = defaultdict(Score)
    for language, text, expected_type, expected in questions:
        started = perf_counter()
        by_rule = read_with_rule(text, DEMO_SHOP)
        rule_seconds = perf_counter() - started
        readings = {"rule": (by_rule, rule_seconds)}
        for model in models:
            started = perf_counter()
            by_model = read_with_model(text, DEMO_SHOP, model)
            model_seconds = perf_counter() - started
            readings[f"model {model}"] = (by_model or by_rule, model_seconds + (rule_seconds if by_model is None else 0))
            if by_rule.type == NOT_SURE:
                usable = by_model is not None and by_model.type != "cannot_answer"
                readings[f"hybrid {model}"] = (by_model if usable else by_rule, rule_seconds + model_seconds)
            else:
                readings[f"hybrid {model}"] = (by_rule, rule_seconds)
        for method, (question, seconds) in readings.items():
            result = outcome(question, expected_type, expected)
            scores[method].add(language, result, seconds)
            if show_misses and result != "right":
                print(f"{method:20} {result:5} [{language}] {text!r} -> {question}")
    return scores


def main() -> None:
    show_misses = "--misses" in sys.argv
    models = [model for model in MODELS if llm.is_on(model)]
    print(f"Models: {', '.join(models) or 'AI is off'}")
    for name, questions in SETS.items():
        scores = score_set(questions, models, show_misses)
        print(f"\n{name} ({len(questions)} questions). Right per language, then right / safe / wrong overall.")
        print(f"{'method':20} {'en':>5} {'fr':>5} {'ar':>5} {'darija':>6} | {'right':>5} {'safe':>5} {'wrong':>5} | ms per question")
        for method, score in scores.items():
            languages = " ".join(f"{score.percent(lang):>{max(5, len(lang))}}" for lang in LANGUAGES)
            average = 1000 * sum(score.seconds) / len(score.seconds)
            print(f"{method:20} {languages} | {score.percent('all'):>5} {score.percent('all', 'safe'):>5} "
                  f"{score.percent('all', 'wrong'):>5} | {average:8.1f} (slowest {1000 * max(score.seconds):.0f})")


if __name__ == "__main__":
    main()
