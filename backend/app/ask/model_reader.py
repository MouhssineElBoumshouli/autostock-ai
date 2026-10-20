"""Understanding a question with the optional local model. It only picks a question type and
filters, as strict JSON from the allowed lists; it never sees or writes numbers.

Filters the chosen type doesn't use are dropped (they would be ignored anyway). Anything else
that isn't allowed makes the whole answer rejected, and the keyword rule is used instead.
"""

from app.ai import llm
from app.ask.question import FILTERS, PERIODS, QUESTION_TYPES, Question, ShopWords, checked_question

TYPE_MEANINGS = {
    "sales_of": "how many pieces were sold (of a part, a category, in a branch, over a period)",
    "best_sellers": "which parts sell the most",
    "running_out": "which parts will run out of stock soon",
    "what_to_order": "what to order from suppliers and what it costs",
    "stock_of_part": "how many of one part are on the shelf",
    "dead_stock": "parts that don't sell anymore",
    "open_alerts": "unusual things the app noticed (alerts)",
    "late_deliveries": "supplier deliveries that are late",
    "forecast_of_part": "how many of one part will sell in the coming days",
    "sales_vs_last": "sales this period compared with the period before",
    "cannot_answer": "anything else: customers, staff, prices, changing or deleting data, other topics",
}

EXAMPLES = """Examples (the shop's names may differ):
"how many headlight bulbs did we sell yesterday in Fes" -> {"type": "sales_of", "part": "headlight bulbs", "category": null, "branch": "Fes - Centre", "period": "yesterday"}
"stock dial les disques" -> {"type": "stock_of_part", "part": "les disques", "category": null, "branch": null, "period": null}
"ما هي قطع المحرك التي ستنفد" -> {"type": "running_out", "part": null, "category": "Engine", "branch": null, "period": null}
"ventes de la semaine dernière comparées à celle d'avant" -> {"type": "sales_vs_last", "part": null, "category": null, "branch": null, "period": "last_week"}
"add 10 batteries to the stock" -> {"type": "cannot_answer", "part": null, "category": null, "branch": null, "period": null}"""


def instructions_for(shop: ShopWords) -> str:
    types = "\n".join(f"- {name}: {meaning}" for name, meaning in TYPE_MEANINGS.items())
    return f"""You read questions from an auto parts shop, in French, English, Arabic or Moroccan Darija.
Reply with JSON only: the question type and its filters. Use null for anything not asked.
Question types:
{types}
Filters:
- part: the words used for the part, copied exactly as typed (keep typos). null if no specific part.
- category: one of {list(shop.categories)} when the question is about a whole category, else null.
- branch: one of {list(shop.branches)} when a branch or its city is named, else null.
- period: one of {list(PERIODS)}, else null. "next month" is not a period.
If the question is not one of the types above, use cannot_answer. Never guess.
{EXAMPLES}"""


def schema_for(shop: ShopWords) -> dict:
    def one_of(values) -> dict:
        return {"enum": [*values, None]}

    return {
        "type": "object",
        "properties": {
            "type": {"enum": list(QUESTION_TYPES)},
            "part": {"type": ["string", "null"]},
            "category": one_of(shop.categories),
            "branch": one_of(shop.branches),
            "period": one_of(PERIODS),
        },
        "required": ["type", *FILTERS],
    }


def read_with_model(text: str, shop: ShopWords) -> Question | None:
    """The model's reading, or None when it is off or its answer is not allowed."""
    raw = llm.ask_json(instructions_for(shop), text, schema_for(shop))
    if isinstance(raw, dict) and raw.get("type") in QUESTION_TYPES:
        used = QUESTION_TYPES[raw["type"]]
        raw = {key: value for key, value in raw.items() if key == "type" or key in used or key not in FILTERS}
    return checked_question(raw, shop)
