"""What a question means once understood: one of a fixed list of question types, plus filters.

Whatever reads the question (the keyword rule or the local model), its result goes through
checked_question, so only these types, these filters and the shop's own names ever reach a query.
"""

from dataclasses import dataclass

QUESTION_TYPES: dict[str, tuple[str, ...]] = {
    # type: the filters it accepts
    "sales_of": ("part", "category", "branch", "period"),
    "best_sellers": ("category", "branch", "period"),
    "running_out": ("category", "branch"),
    "what_to_order": ("category", "branch"),
    "stock_of_part": ("part", "branch"),
    "dead_stock": ("category", "branch"),
    "open_alerts": ("part", "branch"),
    "late_deliveries": (),
    "forecast_of_part": ("part", "branch"),
    "sales_vs_last": ("part", "category", "branch", "period"),
    "today_briefing": (),
    "compare_branches": ("part", "category", "period"),
    "explain_part_change": ("part", "branch", "period"),
    "part_details": ("part", "branch"),
    "cannot_answer": (),
}
PERIODS = ("today", "yesterday", "this_week", "last_week", "this_month", "last_month", "this_year")
FILTERS = ("part", "category", "branch", "period")
PART_TEXT_MAX = 80
NOT_A_PART = {"null", "none"}  # the word for "nothing", written as text


NOT_SURE = "not_sure"  # the rule found words it doesn't understand: it asks instead of guessing


@dataclass(frozen=True)
class Question:
    type: str  # one of QUESTION_TYPES, or NOT_SURE
    part: str | None = None  # for NOT_SURE: the words that weren't understood
    category: str | None = None
    branch: str | None = None
    period: str | None = None
    suggestions: tuple[str, ...] = ()  # for NOT_SURE: the closest question types

    def filters(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in FILTERS if getattr(self, name)}


CANNOT_ANSWER = Question("cannot_answer")


@dataclass(frozen=True)
class ShopWords:
    """The shop's own category and branch names (the only values those filters may take), and
    every word its parts can be called by (names, brands, its synonym list)."""

    categories: tuple[str, ...]
    branches: tuple[str, ...]
    part_words: frozenset[str] = frozenset()


def checked_question(raw: object, shop: ShopWords) -> Question | None:
    """A Question if `raw` is exactly a known type with allowed filters and values, else None."""
    if not isinstance(raw, dict) or raw.get("type") not in QUESTION_TYPES:
        return None
    if set(raw) - {"type", *FILTERS}:
        return None
    allowed = QUESTION_TYPES[raw["type"]]
    values: dict[str, str] = {}
    for name in FILTERS:
        value = raw.get(name)
        if value is None or value == "":
            continue
        if not isinstance(value, str) or name not in allowed:
            return None
        value = value.strip()
        if name == "category" and value not in shop.categories:
            return None
        if name == "branch" and value not in shop.branches:
            return None
        if name == "period" and value not in PERIODS:
            return None
        if name == "part" and (not 0 < len(value) <= PART_TEXT_MAX or value.lower() in NOT_A_PART):
            return None
        values[name] = value
    return Question(raw["type"], **values)
