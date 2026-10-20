"""Honest score for "Ask your shop": the labeled questions (app/ask/blind_test_questions.py) read
by the keyword rule and by the local model, per language, with the time each one takes.

Right = right question type AND every filter right (part compared without little words,
accents or case). The model column is what the app does: the model, and the rule whenever the
model's answer is rejected. Needs Ollama for the model column (docker compose --profile ai up).

Run inside Docker:  docker compose exec api python -m app.ask.check_questions [--misses]
"""

import sys
from collections import defaultdict
from time import perf_counter

from app.ai import llm
from app.ask.blind_test_questions import BLIND_QUESTIONS
from app.ask.keyword_rule import read_with_rule
from app.ask.model_reader import read_with_model
from app.ask.question import Question, ShopWords
from app.ask.words import content_key
from app.config import OLLAMA_MODEL
from app.demo.demo_shop import BRANCHES, FAMILIES

DEMO_SHOP = ShopWords(tuple(sorted({family[1] for family in FAMILIES})), tuple(sorted(BRANCHES)))


def is_right(question: Question, expected_type: str, expected: dict[str, str]) -> bool:
    if question.type != expected_type:
        return False
    if any(getattr(question, name) != expected.get(name) for name in ("category", "branch", "period")):
        return False
    return content_key(question.part or "") == content_key(expected.get("part", ""))


def main() -> None:
    show_misses = "--misses" in sys.argv
    use_model = llm.is_on()
    right: dict[str, dict[str, list[bool]]] = {"rule": defaultdict(list), "model": defaultdict(list)}
    seconds: dict[str, list[float]] = {"rule": [], "model": []}
    rejected = 0

    for language, text, expected_type, expected in BLIND_QUESTIONS:
        started = perf_counter()
        by_rule = read_with_rule(text, DEMO_SHOP)
        seconds["rule"].append(perf_counter() - started)
        for key in (language, "all"):
            right["rule"][key].append(is_right(by_rule, expected_type, expected))
        if show_misses and not right["rule"][language][-1]:
            print(f"rule  miss [{language}] {text!r} -> {by_rule}")

        if use_model:
            started = perf_counter()
            by_model = read_with_model(text, DEMO_SHOP)
            if by_model is None:
                rejected += 1
                by_model = by_rule
            seconds["model"].append(perf_counter() - started)
            for key in (language, "all"):
                right["model"][key].append(is_right(by_model, expected_type, expected))
            if show_misses and not right["model"][language][-1]:
                print(f"model miss [{language}] {text!r} -> {by_model}")

    print(f"{len(BLIND_QUESTIONS)} labeled questions. Model: {OLLAMA_MODEL if use_model else 'AI is off'}")
    print(f"{'language':10} {'questions':>9} {'rule':>7} {'model':>7}")
    for key in ("en", "fr", "ar", "darija", "all"):
        rule_scores = right["rule"][key]
        model_scores = right["model"][key]
        model_text = f"{100 * sum(model_scores) / len(model_scores):6.0f}%" if model_scores else "    off"
        print(f"{key:10} {len(rule_scores):9} {100 * sum(rule_scores) / len(rule_scores):6.0f}% {model_text}")
    for reader, times in seconds.items():
        if times:
            print(f"time per question, {reader}: average {1000 * sum(times) / len(times):.1f} ms, "
                  f"slowest {1000 * max(times):.1f} ms")
    if use_model:
        print(f"model answers rejected (rule used instead): {rejected}")


if __name__ == "__main__":
    main()
