"""Answers about what to order, open alerts and late supplier deliveries."""

from datetime import date

from sqlalchemy import func, select

from app.alerts.problem import pieces
from app.api.today import PENDING_STATUSES, find_late_deliveries
from app.ask.answer_parts import SHOWN_ROWS, Answer, Asked, Number, branch_id, part_not_found, pick_parts, where_words
from app.models import Alert, Branch, OrderRun, OrderSuggestion, Part
from app.shop_day import shop_today


def what_to_order(asked: Asked) -> Answer:
    run = asked.db.scalar(
        select(OrderRun).where(OrderRun.organization_id == asked.organization_id).order_by(OrderRun.created_at.desc()).limit(1)
    )
    if run is None:
        return Answer("what_to_order_no_run", {}, "There is no order suggestion yet. A manager can make one on the Orders page.")
    parts = pick_parts(asked)
    query = (
        select(Part.name, Part.sku, OrderSuggestion.quantity, OrderSuggestion.line_cost)
        .join(Part, Part.id == OrderSuggestion.part_id)
        .where(
            OrderSuggestion.organization_id == asked.organization_id, OrderSuggestion.run_id == run.id,
            OrderSuggestion.status.in_(PENDING_STATUSES), parts.condition,
        )
        .order_by((OrderSuggestion.line_cost if asked.currency else OrderSuggestion.quantity).desc(), Part.sku)
    )
    shop_branch = branch_id(asked)
    if shop_branch:
        query = query.where(OrderSuggestion.branch_id == shop_branch)
    rows = asked.db.execute(query).all()
    made_on = f"latest suggestion, {run.created_at:%d %b}"
    values = {"subject": parts.subject, **asked.place(), "made_on": run.created_at.isoformat()}
    if not rows:
        return Answer("what_to_order_none", values, f"Nothing left to order for {parts.label}{where_words(asked)} ({made_on}).")
    total_pieces = sum(row.quantity for row in rows)
    total_cost = sum(row.line_cost for row in rows)
    return Answer(
        "what_to_order",
        {**values, "count": len(rows), "pieces": total_pieces, **asked.money_value(total_cost)},
        f"To order for {parts.label}{where_words(asked)}: {len(rows)} {'line' if len(rows) == 1 else 'lines'}, "
        f"{pieces(total_pieces)}{asked.money_words(total_cost, ', costing ')} ({made_on}).",
        [
            Number(key="lines_to_order", label="Lines to order", value=len(rows), unit="count"),
            Number(key="pieces_to_order", label="Pieces to order", value=total_pieces, unit="pieces"),
            *asked.money_number("total_cost", "Total cost", total_cost),
        ]
        + [Number(label=f"{name} ({sku})", value=quantity, unit="pieces") for name, sku, quantity, _ in rows[:SHOWN_ROWS]],
    )


def open_alerts(asked: Asked) -> Answer:
    parts = pick_parts(asked)
    if parts is None:
        return part_not_found(asked)
    filters = [Alert.organization_id == asked.organization_id, Alert.status == "open", parts.condition]
    shop_branch = branch_id(asked)
    if shop_branch:
        filters.append(Alert.branch_id == shop_branch)
    total = asked.db.scalar(select(func.count()).select_from(Alert).join(Part, Part.id == Alert.part_id).where(*filters))
    rows = asked.db.execute(
        select(Alert.sentence, Part.name, Branch.name, Alert.kind, Alert.numbers, Alert.started_on)
        .join(Part, Part.id == Alert.part_id)
        .join(Branch, Branch.id == Alert.branch_id)
        .where(*filters)
        .order_by(Alert.raised_on.desc(), Alert.money_at_stake.desc())
        .limit(SHOWN_ROWS)
    ).all()
    values = {"subject": parts.subject, **asked.place()}
    if not total:
        return Answer("open_alerts_none", values, f"No open alerts for {parts.label}{where_words(asked)}.")
    newest = rows[0]
    return Answer(
        "open_alerts",
        {**values, "count": total, "part": newest[1], "alert_branch": newest[2],
         "alert": {"kind": newest.kind, "numbers": newest.numbers, "started_on": newest.started_on.isoformat()}},
        f"{total} open {'alert' if total == 1 else 'alerts'} for {parts.label}{where_words(asked)}. "
        f"Newest: {rows[0].name} in {rows[0][2]}: {rows[0].sentence}",
        [Number(key="open_alerts", label="Open alerts", value=total, unit="count")]
        + [Number(label=f"{row[1]}, {row[2]}", value=row.kind, unit="alert_kind") for row in rows],
    )


def late_deliveries(asked: Asked) -> Answer:
    late = find_late_deliveries(asked.db, asked.organization_id, shop_today())
    if not late:
        return Answer("late_deliveries_none", {}, "No supplier delivery is late.")
    latest = max(late, key=lambda delivery: delivery.days_late)
    return Answer(
        "late_deliveries",
        {"count": len(late), "order_number": latest.order_number, "supplier": latest.supplier_name, "days": latest.days_late},
        f"{len(late)} {'delivery is' if len(late) == 1 else 'deliveries are'} late. Most late: {latest.order_number} "
        f"from {latest.supplier_name}, {latest.days_late} days.",
        [Number(key="late_deliveries", label="Late deliveries", value=len(late), unit="count")]
        + [Number(key="days_late", about=f"{d.order_number}, {d.supplier_name}", label=f"{d.order_number}, {d.supplier_name}, days late",
                  value=d.days_late, unit="days") for d in late[:SHOWN_ROWS]],
    )
