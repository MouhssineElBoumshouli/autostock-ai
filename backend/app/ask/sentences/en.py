"""Answers in English. Each one leads with the most important fact, in short plain sentences."""

from app.ask.sentences.shown import Shown
from app.ask.why import SMALL_CHANGE_PERCENT

FIXED = {
    "busy": "The assistant is busy, try again in a minute.",
    "simple_cannot": "The online assistant isn’t available right now and the app’s simple version can’t answer this question. Try again later.",
    "refusal": "I can't do that. I only read your shop's stock, sales, alerts, orders and suppliers: "
               "I never change data or place orders, and I know nothing about customers or staff.",
    "not_understood": "I didn't understand that question. Try asking it another way, for example “stock of brake pads in Rabat”.",
    "cannot_answer": "I can't answer that yet.",
    "which_part_stock": "Which part? For example: “tell me about the alternator”.",
    "which_part_forecast": "Which part? For example: “how many brake pads will we sell”.",
}
ALERT_KINDS = {
    "sales_spike": "sales much higher than usual", "sales_drop": "sales much lower than usual",
    "sold_at_zero": "sold while stock showed 0", "stock_frozen": "stock count not moving",
    "negative_stock": "stock below zero",
}


def subject(v: dict, s: Shown) -> str | None:
    """"Oil filter - Dacia Logan", "the Brakes category", "oil filters"; None for the whole shop."""
    found = v.get("subject") or {}
    if found.get("kind") == "part":
        return s.name(found["name"])
    if found.get("kind") == "matching":  # the parts' family name ("Oil filter"), else the person's words
        return s.name(found.get("family") or found["words"])
    if found.get("kind") == "category":
        return f"the {s.name(found['name'])} category"
    return None


def _of(v, s) -> str:
    found = subject(v, s)
    return f" of {found}" if found else ""


def _in(v, s, key: str = "branch") -> str:
    return f" in {s.name(v[key])}" if v.get(key) else ""


def _change(percent, s: Shown) -> str:
    if percent is None:
        return "no sales before"
    if percent == 0:
        return "the same"
    return f"{'up' if percent > 0 else 'down'} {s.percent(percent)}"


def sales_of(v, s):
    worth = f", worth {s.money(v['money'])}" if "money" in v else ""
    return f"{s.pieces(v['pieces'])}{_of(v, s)} sold{_in(v, s)} {s.period(v['period'])} ({s.range(v['range'])}){worth}."


def best_sellers(v, s):
    text = (f"The best seller{_of(v, s)}{_in(v, s)} {s.period(v['period'])} is {s.name(v['name'])}: "
            f"{s.pieces(v['pieces'])} sold.")
    others = [f"{s.name(row['name'])} ({s.number(row['pieces'])})" for row in v.get("next", [])]
    if others:
        text += f" Next: {' and '.join(others)}."
    return text


def best_sellers_none(v, s):
    return f"No sales{_of(v, s)}{_in(v, s)} {s.period(v['period'])} ({s.range(v['range'])})."


def sales_vs_last(v, s):
    sales = f"Sales{_of(v, s)}{_in(v, s)}"
    now = f"{s.pieces(v['pieces'])} {s.period(v['period'])} ({s.range(v['range'])})"
    if v["percent"] is None:
        return f"{sales}: {now}, and none in the period before ({s.range(v['before_range'])})."
    if v["percent"] == 0:
        return f"{sales} are unchanged: {now}, the same as before ({s.range(v['before_range'])})."
    way = "up" if v["percent"] > 0 else "down"
    return (f"{sales} are {way} {s.percent(v['percent'])}: {now}, "
            f"against {s.number(v['before_pieces'])} before ({s.range(v['before_range'])}).")


def stock_of_part(v, s):
    if not v["pieces"]:
        return f"No stock left{_of(v, s)}{_in(v, s)}."
    return f"{s.pieces(v['pieces'])}{_of(v, s)} in stock{_in(v, s)}."


def running_out(v, s):
    parts = "1 part" if v["count"] == 1 else f"{s.number(v['count'])} parts"
    return (f"{parts}{_of_list(v, s)} may run out{_in(v, s)} within {s.days(v['days'])}. "
            f"First: {s.name(v['name'])}, {s.pieces(v['pieces'])} left, about {s.days(v['days_left'])}.")


def _of_list(v, s) -> str:
    found = subject(v, s)
    return f" ({found})" if found else ""


def running_out_none(v, s):
    return f"Nothing{_of_list(v, s)} should run out{_in(v, s)} in the next {s.days(v['days'])}."


def dead_stock(v, s):
    parts = "1 part has" if v["count"] == 1 else f"{s.number(v['count'])} parts have"
    worth = f", worth {s.money(v['money'])} at cost" if "money" in v else ""
    return f"{parts} not sold in {s.days(v['days'])}{_of_list(v, s)}{_in(v, s)}: {s.pieces(v['pieces'])} on the shelf{worth}."


def dead_stock_none(v, s):
    return f"Everything in stock{_of_list(v, s)}{_in(v, s)} sold at least once in the last {s.days(v['days'])}."


def forecast(v, s):
    return (f"About {s.pieces(v['pieces'])}{_of(v, s)} should sell{_in(v, s)} in the next {s.days(v['days'])} "
            f"(likely between {s.number(v['low'])} and {s.number(v['high'])}).")


def forecast_none(v, s):
    return f"No forecast yet{_of_list(v, s)}. Forecasts are made after sales are imported."


def what_to_order(v, s):
    lines = "1 line" if v["count"] == 1 else f"{s.number(v['count'])} lines"
    cost = f", costing {s.money(v['money'])}" if "money" in v else ""
    return (f"You should order {s.pieces(v['pieces'])}{_of_list(v, s)}{_in(v, s)}, in {lines}{cost}. "
            f"This is the suggestion made on {s.day(v['made_on'])}.")


def what_to_order_none(v, s):
    return f"Nothing left to order{_of_list(v, s)}{_in(v, s)} (suggestion made on {s.day(v['made_on'])})."


def what_to_order_no_run(v, s):
    return "There is no order suggestion yet. A manager can make one on the Orders page."


def open_alerts(v, s):
    alerts = "1 open alert" if v["count"] == 1 else f"{s.number(v['count'])} open alerts"
    kind = ALERT_KINDS.get(v["alert"]["kind"], v["alert"]["kind"])
    return (f"{alerts}{_of_list(v, s)}{_in(v, s)}. The newest: {s.name(v['part'])} in "
            f"{s.name(v['alert_branch'])}, {kind}.")


def open_alerts_none(v, s):
    return f"No open alerts{_of_list(v, s)}{_in(v, s)}."


def late_deliveries(v, s):
    late = "1 delivery is late" if v["count"] == 1 else f"{s.number(v['count'])} deliveries are late"
    return f"{late}. The latest: order {s.name(v['order_number'])} from {s.name(v['supplier'])}, {s.days(v['days'])} late."


def late_deliveries_none(v, s):
    return "No supplier delivery is late."


def today_briefing(v, s):
    text = _briefing_sales(v, s)
    needs, worth = v["needs_action"]["count"], v["worth_a_look"]["count"]
    text += f" {s.number(needs)} alerts need you, {s.number(worth)} are worth a look."
    lines = v["to_order"]["lines"]
    text += f" To order: {s.number(lines)} lines." if lines else " Nothing to order."
    late = v["late_deliveries"]["count"]
    text += f" {s.number(late)} late deliveries." if late else " No late deliveries."
    running = v["running_out"]["count"]
    if running:
        text += f" {s.number(running)} parts may run out within {s.days(v['running_out']['within_days'])}."
    return text


def _briefing_sales(v, s) -> str:
    if "sales_in_period" in v:
        period = v["sales_in_period"]
        when = s.period(period["period"])
        return (f"{when[:1].upper()}{when[1:]} ({s.range(period['range'])}): {s.pieces(period['pieces'])} sold, "
                f"{_change(period['percent'], s)} on the period before ({s.number(period['before_pieces'])}). Right now:")
    week = v.get("sales_this_week")
    if not week:
        return "No sales yet."
    if week["percent_vs_normal"] in (None, 0):
        compared = f"a normal week is {s.number(week['normal_week'])}"
    else:
        compared = f"{_change(week['percent_vs_normal'], s)} on a normal week ({s.number(week['normal_week'])})"
    return f"This week: {s.pieces(week['pieces'])} sold, {compared}."


def compare_branches(v, s):
    rows = v["branches"]
    when = f"{s.period(v['period'])} ({s.range(v['range'])})"
    if not rows or not rows[0]["pieces"]:
        return f"No sales{_of(v, s)} {when} in any branch."
    top, others = rows[0], rows[1:]
    most = "more" if v.get("only_asked") and len(rows) == 2 else "the most"
    text = f"{s.name(top['branch'])} sells {most}{_of(v, s)}: {s.pieces(top['pieces'])} {when}"
    if others:
        listed = [f"{s.name(row['branch'])} ({s.number(row['pieces'])})" for row in others]
        text += f", ahead of {', '.join(listed[:-1]) + ' and ' + listed[-1] if len(listed) > 1 else listed[0]}"
    changes = [f"{s.name(row['branch'])} {_change(row['percent_change'], s)}" for row in rows]
    return f"{text}. Against the period before: {', '.join(changes)}."


def explain_part_change(v, s):
    sales = f"Sales{_of(v, s)}{_in(v, s)}"
    numbers = f"{s.number(v['pieces_now'])} {s.period(v['period'])} against {s.number(v['pieces_before'])} before"
    if v["direction"] == "same":
        return f"{sales} have not really changed: {numbers}."
    head = f"{sales} are {_way(v, s)}: {numbers}."
    reasons = v["reasons"]
    if not reasons:
        return (f"{head} I see no clear reason in the data: stock, prices, alerts and last year "
                f"don't explain it.")
    main = f"{head} Main reason: {_reason(reasons[0], v, s)}."
    if len(reasons) > 1:
        main += f" Also: {_reason(reasons[1], v, s)}."
    return main


def _way(v, s) -> str:
    """"down 12%", or "down a little (4%)" for a small change."""
    way = "down" if v["direction"] == "down" else "up"
    if v["percent_change"] is None:
        return way
    if abs(v["percent_change"]) < SMALL_CHANGE_PERCENT:
        return f"{way} a little ({s.percent(v['percent_change'])})"
    return f"{way} {s.percent(v['percent_change'])}"


def _reason(reason: dict, v, s) -> str:
    over = {"parts_and_branches": " (in total, all these parts and branches together)", "branches": " (in total, all branches together)"}
    counted = over.get(v.get("days_out_of_stock_counts"), "")
    kind = reason["kind"]
    if kind == "out_of_stock":
        return f"out of stock {s.days(reason['days_now'])} {s.period(v['period'])}{counted}, against {s.number(reason['days_before'])} before"
    if kind == "back_in_stock":
        return f"back in stock: out {s.days(reason['days_before'])} before{counted}, only {s.number(reason['days_now'])} now"
    if kind in ("price_up", "price_down"):
        prices = f" ({s.money(reason['price_before'])} to {s.money(reason['price_now'])})" if "price_now" in reason else ""
        return f"the average price went {'up' if kind == 'price_up' else 'down'} {s.percent(reason['percent'])}{prices}"
    if kind == "season":
        return f"normal for the season, the same days last year sold {s.number(reason['last_year'])}"
    return f"an open alert in {s.name(reason['branch'])}: {ALERT_KINDS.get(reason['alert_kind'], reason['alert_kind'])}"


def part_details(v, s):
    totals = v["totals"]
    best = v["parts"][0]
    text = (f"{_capital(subject(v, s)) or 'These parts'}{_in(v, s)}: {s.pieces(totals['stock_total'])} in stock, "
            f"{s.number(totals['sold_last_30_days'])} sold in the last 30 days, "
            f"about {s.number(totals['expected_next_30_days'])} expected in the next 30 days.")
    if v["matches"] > 1:
        text += f" {s.number(v['matches'])} parts match; the best seller is {s.name(best['name'])}."
    return text


def _capital(text: str | None) -> str | None:
    return text[:1].upper() + text[1:] if text else text


def part_not_found(v, s):
    return f"I couldn't find a part called “{s.name(v['part'])}”. Try its name or part number."


def not_sure(v, s):
    by = f" by “{s.name(v['words'])}”" if v.get("words") else ""
    return "I'm not sure what you mean{by}. Did you mean one of these?".format(by=by)
