"""The assistant's READ-ONLY tools over the shop's data. Every tool is scoped to the asker's shop; people
who don't see money (staff) never get a money field.

run_tool() checks the tool name, runs it in the given (read-only) session and returns the result, or the
exact error for the assistant to fix its call.
"""

from collections.abc import Callable

from app.ask.data_tools.context import Asker, ToolError, ToolResult
from app.ask.data_tools.parts import SPEC as PARTS_SPEC
from app.ask.data_tools.parts import parts
from app.ask.data_tools.running_out import SPEC as RUNNING_OUT_SPEC
from app.ask.data_tools.running_out import running_out
from app.ask.data_tools.sales import SPEC as SALES_SPEC
from app.ask.data_tools.sales import sales
from app.ask.data_tools.sales_change import SPEC as WHY_SALES_SPEC
from app.ask.data_tools.sales_change import why_sales
from app.ask.data_tools.stock import STOCK_OUTS_SPEC, STOCK_SPEC, stock, stock_outs
from app.ask.data_tools.supply import SPEC as ORDERS_SPEC
from app.ask.data_tools.supply import orders
from app.ask.data_tools.watch import ALERTS_SPEC, FORECAST_SPEC, alerts, forecast

TOOLS: dict[str, tuple[dict, Callable[[Asker, dict], ToolResult]]] = {
    "parts": (PARTS_SPEC, parts),
    "stock": (STOCK_SPEC, stock),
    "sales": (SALES_SPEC, sales),
    "why_sales": (WHY_SALES_SPEC, why_sales),
    "running_out": (RUNNING_OUT_SPEC, running_out),
    "stock_outs": (STOCK_OUTS_SPEC, stock_outs),
    "forecast": (FORECAST_SPEC, forecast),
    "orders": (ORDERS_SPEC, orders),
    "alerts": (ALERTS_SPEC, alerts),
}


def tool_specs(sees_money: bool) -> list[dict]:
    """The tools, in the format the model reads (the same for everyone: money is left out of the results)."""
    return [{"type": "function", "function": spec} for spec, _ in TOOLS.values()]


def run_tool(asker: Asker, name: str, args: object) -> ToolResult:
    if name not in TOOLS:
        return ToolResult({"error": f"Unknown tool '{name}'."})
    if not isinstance(args, dict):
        return ToolResult({"error": "Arguments must be a JSON object."})
    try:
        return TOOLS[name][1](asker, args)
    except ToolError as error:
        return ToolResult(error.details)
