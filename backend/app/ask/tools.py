"""The read-only lookups the assistant's model may call. Each one runs the app's own queries, scoped
to the asker's shop; people who don't see money get no money. The model only chooses which lookups
and with which filters: every filter is matched to the shop's own names before any query runs.
"""

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ask.answer_parts import Answer, Asked, shop_today
from app.ask.answers import ANSWERS
from app.ask.keyword_rule import branch_named, category_named
from app.ask.overview_answers import compare_branches, today_briefing
from app.ask.part_answers import explain_part_change, part_details
from app.ask.question import PART_TEXT_MAX, PERIODS, Question, ShopWords

PART = "the part as the person called it, in their words (\"brake pads\", \"plaquettes\", \"البطارية\")"


@dataclass(frozen=True)
class Tool:
    description: str
    filters: tuple[str, ...]
    build: Callable[[Asked], Answer]
    needs_part: bool = False


TOOLS: dict[str, Tool] = {
    "today_briefing": Tool(
        "Today's overview: this week's sales vs a normal week, alerts that need action or are worth a look, "
        "what to order, late supplier deliveries, parts running out. Use it for open questions like "
        "'what's going on', 'how are we doing', 'what should I worry about'.", (), today_briefing),
    "compare_branches": Tool(
        "Pieces sold per branch, most first, each compared with the period before.",
        ("part", "category", "period"), compare_branches),
    "explain_part_change": Tool(
        "Why one part's sales changed: sales now vs before vs last year, week by week, days out of stock, "
        "open alerts, stock now, forecast.", ("part", "branch", "period"), explain_part_change, needs_part=True),
    "part_details": Tool(
        "Everything about one part: stock per branch, sales in the last 30 days, forecast, alerts, prices.",
        ("part", "branch"), part_details, needs_part=True),
    "sales_of": Tool("How many pieces were sold.", ("part", "category", "branch", "period"), ANSWERS["sales_of"]),
    "best_sellers": Tool("The parts that sold the most.", ("category", "branch", "period"), ANSWERS["best_sellers"]),
    "sales_vs_last": Tool(
        "Pieces sold in a period compared with the period just before.",
        ("part", "category", "branch", "period"), ANSWERS["sales_vs_last"]),
    "stock_of_part": Tool("How many of a part are in stock, per branch.", ("part", "branch"), ANSWERS["stock_of_part"],
                          needs_part=True),
    "running_out": Tool("Parts expected to run out of stock within 14 days.", ("category", "branch"), ANSWERS["running_out"]),
    "what_to_order": Tool("What the latest order suggestion says to order from suppliers.", ("category", "branch"),
                          ANSWERS["what_to_order"]),
    "dead_stock": Tool("Parts with stock but no sale in 90 days.", ("category", "branch"), ANSWERS["dead_stock"]),
    "open_alerts": Tool("Unusual things the app noticed (sales spikes and drops, stock problems).", ("part", "branch"),
                        ANSWERS["open_alerts"]),
    "late_deliveries": Tool("Supplier deliveries that are late.", (), ANSWERS["late_deliveries"]),
    "forecast_of_part": Tool("How many pieces of a part are expected to sell in the next 30 days.", ("part", "branch"),
                             ANSWERS["forecast_of_part"], needs_part=True),
}
MOST_CALLS = 6  # in one answer


@dataclass
class Lookup:
    """One tool call: what was used, and what came back."""

    tool: str
    filters: dict[str, str]
    answer: Answer | None  # None when the call itself was refused (unknown tool, a branch the shop doesn't have)
    problem: str | None = None


def tool_specs() -> list[dict]:
    """The tools in Ollama's format. The shop's branches and categories are listed once, in the
    instructions (see shop_names), not in every tool: a shorter prompt is a faster answer."""
    properties = {
        "part": {"type": "string", "description": PART},
        "category": {"type": "string", "description": "one of the shop's categories"},
        "branch": {"type": "string", "description": "one of the shop's branches"},
        "period": {"type": "string", "enum": list(PERIODS), "description": "leave out for the last 30 days"},
    }
    return [
        {"type": "function", "function": {
            "name": name, "description": tool.description,
            "parameters": {"type": "object", "properties": {f: properties[f] for f in tool.filters},
                           "required": ["part"] if tool.needs_part else []},
        }}
        for name, tool in TOOLS.items()
    ]


def shop_names(shop: ShopWords) -> str:
    return f"The shop's branches: {', '.join(shop.branches)}. Its categories: {', '.join(shop.categories)}."


def checked_filters(tool: Tool, arguments: object, shop: ShopWords) -> tuple[dict[str, str], str | None]:
    """The filters matched to the shop's own names, or a problem the model is told about."""
    if not isinstance(arguments, dict):
        return {}, "Arguments must be an object."
    filters: dict[str, str] = {}
    for name, value in arguments.items():
        if name not in tool.filters or value in (None, ""):
            continue  # filters a tool doesn't take are ignored, as the old reader did
        if not isinstance(value, str):
            return {}, f"{name} must be text."
        value = value.strip()
        if name == "branch":
            filters[name] = branch_named(value, shop.branches) or ""
            if not filters[name]:
                return {}, f"There is no branch called {value!r}. Branches: {', '.join(shop.branches)}."
        elif name == "category":
            filters[name] = category_named(value, shop.categories) or ""
            if not filters[name]:
                return {}, f"There is no category called {value!r}. Categories: {', '.join(shop.categories)}."
        elif name == "period":
            if value not in PERIODS:
                return {}, f"period must be one of {', '.join(PERIODS)}, or left out for the last 30 days."
            filters[name] = value
        elif 0 < len(value) <= PART_TEXT_MAX:
            filters[name] = value
    return filters, None


def look_up(db: Session, organization_id: uuid.UUID, currency: str | None, shop: ShopWords, name: str, arguments: object) -> Lookup:
    tool = TOOLS.get(name)
    if tool is None:
        return Lookup(name, {}, None, f"There is no tool called {name!r}.")
    filters, problem = checked_filters(tool, arguments, shop)
    if problem:
        return Lookup(name, {}, None, problem)
    asked = Asked(db, organization_id, Question(name, **filters), shop_today(db, organization_id), currency)
    answer = tool.build(asked)
    if currency is None:
        answer.numbers = [number for number in answer.numbers if number.unit != "money"]
    return Lookup(name, filters, answer)


def for_the_model(lookup: Lookup, currency: str | None) -> str:
    """What the model reads back: the app's own sentence, the facts and the numbers. Money is in the
    shop's currency (not centimes), so the model never has to convert it."""
    if lookup.answer is None:
        return json.dumps({"problem": lookup.problem})
    answer = lookup.answer
    numbers = [
        {"label": number.label, "value": _money(number.value) if number.unit == "money" else number.value}
        for number in answer.numbers
    ]
    content = {"filters_used": lookup.filters, "summary": answer.sentence, "facts": _with_money(answer.values), "numbers": numbers}
    if currency:
        content["currency"] = currency
    return json.dumps(content, ensure_ascii=False, default=str)


def _money(centimes: object) -> object:
    return centimes / 100 if isinstance(centimes, int) else centimes


def _with_money(value: object, key: str = "") -> object:
    if isinstance(value, dict):
        return {k: _with_money(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_with_money(v) for v in value]
    return _money(value) if key == "money" or key.endswith("_money") else value
