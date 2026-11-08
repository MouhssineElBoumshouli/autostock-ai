"""The assistant's READ-ONLY tools over the shop's data. Every tool is scoped to the asker's shop; people
who don't see money (staff) never get a money field, and never get the prices tool at all.

run_tool() checks the tool name, runs it in the given (read-only) session and returns the result, or the
exact error for the assistant to fix its call.
"""

from collections.abc import Callable

from app.ask.data_tools.context import Asker, ToolError, ToolResult
from app.ask.data_tools.parts import FIND_PARTS_SPEC, PRICES_SPEC, find_parts, prices
from app.ask.data_tools.sales import SPEC as SALES_SPEC
from app.ask.data_tools.sales import sales
from app.ask.data_tools.stock import STOCK_OUTS_SPEC, STOCK_SPEC, stock, stock_outs
from app.ask.data_tools.supply import (
    ORDER_SUGGESTIONS_SPEC, PURCHASE_ORDERS_SPEC, SUPPLIERS_SPEC, order_suggestions, purchase_orders, suppliers,
)
from app.ask.data_tools.watch import ALERTS_SPEC, FORECAST_SPEC, alerts, forecast

TOOLS: dict[str, tuple[dict, Callable[[Asker, dict], ToolResult]]] = {
    "find_parts": (FIND_PARTS_SPEC, find_parts),
    "stock": (STOCK_SPEC, stock),
    "sales": (SALES_SPEC, sales),
    "stock_outs": (STOCK_OUTS_SPEC, stock_outs),
    "forecast": (FORECAST_SPEC, forecast),
    "order_suggestions": (ORDER_SUGGESTIONS_SPEC, order_suggestions),
    "purchase_orders": (PURCHASE_ORDERS_SPEC, purchase_orders),
    "alerts": (ALERTS_SPEC, alerts),
    "suppliers": (SUPPLIERS_SPEC, suppliers),
    "prices": (PRICES_SPEC, prices),
}
MONEY_ONLY = {"prices"}


def tool_specs(sees_money: bool) -> list[dict]:
    """The tools offered to this person, in the format the model reads."""
    return [{"type": "function", "function": spec} for name, (spec, _) in TOOLS.items()
            if sees_money or name not in MONEY_ONLY]


def run_tool(asker: Asker, name: str, args: object) -> ToolResult:
    if name not in TOOLS or (name in MONEY_ONLY and not asker.sees_money):
        return ToolResult({"error": f"Unknown tool '{name}'."})
    if not isinstance(args, dict):
        return ToolResult({"error": "Arguments must be a JSON object."})
    try:
        return TOOLS[name][1](asker, args)
    except ToolError as error:
        return ToolResult(error.details)
