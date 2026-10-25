"""The facts the writer may use, each with a label instead of its number: [F1] = Rabat - Agdal,
pieces sold, this period = 4288. The writer types labels; the app puts the real, formatted numbers
in their place (app/ask/fact_check.py). Each fact knows what it belongs to (a branch, a part, a
period), so a label can be checked against the words around it.
"""

from dataclasses import dataclass

from app.ask.answer_parts import Answer
from app.ask.question import Question

MOST_FACTS = 40
MOST_ROWS = 6  # of a list (branches, parts): the writer doesn't need more
# Dates are left out: the writer says "this week" or "the period before", and the dates are shown
# under the answer anyway. So are words and details the writer doesn't need.
SKIPPED = {"subject", "kind", "words", "what", "alert", "numbers", "weekly_pieces", "days_out_of_stock_counts",
           "sku", "period", "category", "status", "top", "range", "before_range", "day", "made_from", "made_on",
           "started_on", "week", "from", "to", "normal_week_is_average_of_weeks", "within_days", "days"}
# The most important facts first, so the writer leads with them.
FIRST = ("sales_this_week", "needs_action", "to_order", "running_out", "late_deliveries", "worth_a_look")
# What a number is, in plain words, by its key (or "parent key" when the parent says more).
WHAT = {
    "pieces": "pieces sold", "pieces_now": "pieces sold", "pieces_before": "pieces sold", "before_pieces": "pieces sold",
    "same_days_last_year": "pieces sold", "normal_week": "pieces sold", "total_pieces": "pieces sold, all branches together",
    "money": "sales value", "to_order money": "cost of what to order", "percent": "change in pieces sold",
    "percent_change": "change in pieces sold", "percent_vs_normal": "change compared with a normal week",
    "needs_action count": "alerts that need action", "worth_a_look count": "alerts worth a look",
    "late_deliveries count": "late supplier deliveries", "running_out count": "parts running out within 14 days",
    "count": "how many", "lines": "lines to order", "stock_total": "pieces in stock", "stock_now": "pieces in stock",
    "totals stock_total": "pieces in stock, all matching parts", "sold_last_30_days": "pieces sold in the last 30 days",
    "totals sold_last_30_days": "pieces sold in the last 30 days, all matching parts",
    "expected_next_30_days": "pieces expected to sell in the next 30 days",
    "totals expected_next_30_days": "pieces expected to sell in the next 30 days, all matching parts",
    "days_out_of_stock_now": "days out of stock (counted per branch)",
    "days_out_of_stock_before": "days out of stock (counted per branch)", "min_stock": "minimum stock",
    "open_alerts": "open alerts", "matches": "matching parts", "sale_price_money": "sale price",
    "unit_cost_money": "unit cost", "low": "likely at least", "high": "likely at most", "days_left": "days left",
    "days_late": "days late", "stock_by_branch pieces": "pieces in stock",
}
PART_KEYS = ("name", "supplier", "order_number")
# What period a fact is about. "now" is given to every other fact of an answer that compares periods.
WHEN_WORDS = {"now": "this period", "before": "the period before", "last_year": "the same days last year",
              "normal": "a normal week"}


@dataclass(frozen=True)
class Fact:
    label: str  # "F1"
    what: str  # "pieces", "pieces before" (English, for the writer)
    value: object  # as the app has it (money in the shop's currency, not centimes)
    shown: str  # what replaces the label in the answer: "4 288", "+5 %", "1 212 274,00 DH"
    branch: str | None = None
    part: str | None = None  # a part, supplier or order the number belongs to
    when: str | None = None  # a key of WHEN_WORDS
    direction: str | None = None  # a change: "up", "down" or "same"

    def line(self) -> str:
        """[F1] Rabat - Agdal · this period · pieces. The writer never sees the number itself, so it
        can't copy it; a percentage says which way it goes."""
        context = " · ".join(x for x in (self.branch, self.part, WHEN_WORDS.get(self.when or ""), self.what) if x)
        if self.direction:
            context += f" ({self.direction})"
        return f"[{self.label}] {context}"


def labeled_facts(answer: Answer, question: Question, currency: str | None, language: str) -> list[Fact]:
    """`language` is "en", "fr" or "ar": how the numbers are written in the answer."""
    found: list[dict] = []
    _walk(answer.values, [], {"branch": question.branch}, found)
    compares = any(fact["when"] for fact in found)
    facts = []
    for number, fact in enumerate(found[:MOST_FACTS], 1):
        when = fact["when"] or ("now" if compares and not fact["key"].startswith("percent") else None)
        facts.append(Fact(
            label=f"F{number}", what=fact["what"], value=_raw(fact["value"], fact["key"], currency),
            shown=_shown(fact["value"], fact["key"], currency, language), branch=fact["branch"],
            part=fact["part"], when=when, direction=_direction(fact["value"]) if fact["key"].startswith("percent") else None,
        ))
    return facts


def _direction(percent: float) -> str:
    return "up" if percent > 0 else "down" if percent < 0 else "same"


def _when_of(key: str) -> str | None:
    if key.startswith("percent"):
        return None
    if "last_year" in key:
        return "last_year"
    if "before" in key:
        return "before"
    if "normal" in key:
        return "normal"
    return None


def _walk(value: object, path: list[str], around: dict, found: list[dict]) -> None:
    key = path[-1] if path else ""
    if isinstance(value, dict):
        inside = dict(around)
        if path and path[-1] == "#":  # an item of a list: its own branch and part
            inside["branch"] = value.get("branch") or value.get("alert_branch") or around.get("branch")
            inside["part"] = next((value[k] for k in PART_KEYS if isinstance(value.get(k), str)), around.get("part"))
        inside["when"] = _when_of(key) or around.get("when")
        for name, item in sorted(value.items(), key=lambda pair: (pair[0] not in FIRST, FIRST.index(pair[0]) if pair[0] in FIRST else 0)):
            if name not in SKIPPED and not (path and path[-1] == "#" and name in ("branch", *PART_KEYS)):
                _walk(item, [*path, name], inside, found)
    elif isinstance(value, list):
        for item in value[:MOST_ROWS]:
            _walk(item, [*path, "#"], around, found)
    elif isinstance(value, bool) or value is None:
        return
    elif isinstance(value, int | float):
        steps = [step for step in path if step != "#"]
        parent = f"{steps[-2]} {key}" if len(steps) > 1 else key
        found.append({
            "key": key, "value": value, "branch": around.get("branch"), "part": around.get("part"),
            "when": _when_of(key) or around.get("when"),
            "what": WHAT.get(parent) or WHAT.get(key) or " ".join(step.replace("_", " ") for step in steps),
        })


def _is_money(key: str) -> bool:
    return key == "money" or key.endswith("_money")


def _raw(value: object, key: str, currency: str | None) -> object:
    if _is_money(key) and isinstance(value, int):
        return f"{value / 100:.2f} {currency}"
    if key.startswith("percent"):
        return f"{value:+}%"
    return value


def _shown(value: float, key: str, currency: str | None, language: str) -> str:
    if _is_money(key):
        amount = _grouped(value / 100, language, decimals=2)
        return f"{currency} {amount}" if language == "en" else f"{amount} {'DH' if currency == 'MAD' else currency}"
    if key.startswith("percent"):
        return f"{value:+}{'%' if language != 'fr' else ' %'}"
    return _grouped(value, language)


def _grouped(value: float, language: str, decimals: int = 0) -> str:
    """1,234.50 in English; 1 234,50 in French and Arabic (digits stay 0-9, as on the website)."""
    text = f"{value:,.{decimals}f}"
    if language == "en":
        return text
    return text.replace(",", " ").replace(".", ",")
