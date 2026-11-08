"""Open alerts (unusual sales, stock that doesn't match sales) and the app's demand forecasts, with how
each forecast did against the simple baseline ("average of the last weeks") on past data."""

from sqlalchemy import func, select

from app.ask.answer_parts import Number
from app.ask.data_tools.context import PART, TEXT, TOP, Asker, ToolError, ToolResult, asked_heading, branch_choice, part_choice, rows_wanted
from app.models import Alert, Branch, Forecast, Part

ALERTS_SPEC = {
    "name": "alerts",
    "description": "Open alerts (sales spikes/drops, stock not matching sales), newest first.",
    "parameters": {"type": "object", "properties": {**PART, "branch": TEXT, **TOP}},
}
FORECAST_SPEC = {
    "name": "forecast",
    "description": "Pieces expected to sell in the next 7/30/60 days, and vs the simple baseline.",
    "parameters": {"type": "object", "properties": {
        **PART, "branch": TEXT, "days": {"enum": [7, 30, 60]}, "group_by": {"enum": ["part", "branch"]}, **TOP}},
}


def alerts(asker: Asker, args: dict) -> ToolResult:
    parts = part_choice(asker, args)
    branch_id, branch = branch_choice(asker, args)
    filters = [Alert.organization_id == asker.organization_id, Alert.status == "open", parts.condition]
    if branch_id:
        filters.append(Alert.branch_id == branch_id)
    rows = asker.db.execute(
        select(Part.name, Part.brand, Branch.name, Alert.kind, Alert.sentence, Alert.started_on, Alert.money_at_stake)
        .join(Part, Part.id == Alert.part_id).join(Branch, Branch.id == Alert.branch_id).where(*filters)
        .order_by(Alert.raised_on.desc(), Alert.money_at_stake.desc())
    ).all()
    data = {"open_alerts": len(rows), "rows": [
        {"part": f"{row[0]} ({row[1] or ''})", "branch": row[2], "kind": row.kind, "what": row.sentence,
         "since": row.started_on.isoformat(), **({"money_at_stake": asker.money(row.money_at_stake)} if asker.sees_money else {})}
        for row in rows[:rows_wanted(args)]]}
    if branch:
        data["branch"] = branch
    shown = [Number(key="open_alerts", label="Open alerts", value=len(rows), unit="count")]
    shown += [Number(label=f"{row['part']}, {row['branch']}", value=row["kind"], unit="alert_kind") for row in data["rows"][:8]]
    return ToolResult(data, shown, asked_heading(parts, branch))


def forecast(asker: Asker, args: dict) -> ToolResult:
    parts = part_choice(asker, args)
    branch_id, branch = branch_choice(asker, args)
    days = args.get("days") if args.get("days") in (7, 30, 60) else 30
    filters = [Forecast.organization_id == asker.organization_id, Forecast.horizon_days == days, parts.condition]
    if branch_id:
        filters.append(Forecast.branch_id == branch_id)
    base = select().select_from(Forecast).join(Part, Part.id == Forecast.part_id).join(Branch, Branch.id == Forecast.branch_id)
    beats = func.count().filter(Forecast.method_wape < Forecast.baseline_wape)
    expected, low, high, made_from, count, beat = asker.db.execute(base.add_columns(
        func.sum(Forecast.quantity), func.sum(Forecast.low), func.sum(Forecast.high), func.max(Forecast.history_last_day),
        func.count(), beats).where(*filters)).one()
    if not count:
        raise ToolError("No forecast for these parts yet. Forecasts are made on the Forecasts page.")
    data = {"days": days, "expected_pieces": round(expected), "likely_range": [round(low), round(high)],
            "from_sales_up_to": made_from.isoformat() if made_from else None, "forecasts": count,
            "beat_the_baseline": beat}
    if branch:
        data["branch"] = branch
    group = {"part": Part.name + " (" + func.coalesce(Part.brand, "") + ")", "branch": Branch.name}.get(args.get("group_by"))
    if group is not None:
        rows = asker.db.execute(base.add_columns(group.label("name"), func.sum(Forecast.quantity).label("pieces"))
                                .where(*filters).group_by(group).order_by(func.sum(Forecast.quantity).desc())
                                .limit(rows_wanted(args))).all()
        data["rows"] = [{"name": row.name, "expected_pieces": round(row.pieces)} for row in rows]
    shown = [Number(key="expected_pieces", label="Expected pieces", value=data["expected_pieces"], unit="pieces",
                    about=str(days))]
    shown += [Number(key="expected_about", label=row["name"], about=row["name"], value=row["expected_pieces"], unit="pieces")
              for row in data.get("rows", [])[:8]]
    return ToolResult(data, shown, {**asked_heading(parts, branch), "days": str(days)})
