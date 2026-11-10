"""الأجوبة بالعربية. كل جواب يبدأ بأهم معلومة، بجمل قصيرة وبسيطة. Darija questions are answered here too."""

from app.ask.sentences.shown import Shown
from app.ask.why import SMALL_CHANGE_PERCENT

FIXED = {
    "busy": "المساعد مشغول، أعد المحاولة بعد دقيقة.",
    "simple_cannot": "المساعد عبر الإنترنت غير متاح حاليًا، والنسخة البسيطة من التطبيق لا تعرف الإجابة عن هذا السؤال. أعد المحاولة لاحقًا.",
    "refusal": "لا أستطيع فعل ذلك. أنا أقرأ فقط المخزون والمبيعات والتنبيهات والطلبيات والموردين: "
               "لا أغير أي بيانات ولا أضع طلبيات، ولا أعرف شيئا عن الزبائن أو الموظفين.",
    "not_understood": "لم أفهم السؤال. جرّب أن تطرحه بطريقة أخرى، مثلا «مخزون الفرامل في الرباط».",
    "cannot_answer": "لا أستطيع الإجابة عن هذا السؤال بعد.",
    "which_part_stock": "أي قطعة؟ مثلا: «أعطني تفاصيل عن المولد».",
    "which_part_forecast": "أي قطعة؟ مثلا: «كم سنبيع من الفرامل».",
}
ALERT_KINDS = {
    "sales_spike": "مبيعات أعلى بكثير من المعتاد", "sales_drop": "مبيعات أقل بكثير من المعتاد",
    "sold_at_zero": "بيع والمخزون يُظهر 0", "stock_frozen": "رقم المخزون لا يتحرك", "negative_stock": "مخزون تحت الصفر",
}


def subject(v: dict, s: Shown) -> str | None:
    found = v.get("subject") or {}
    if found.get("kind") == "part":
        return s.name(found["name"])
    if found.get("kind") == "matching":  # the parts' family name ("Oil filter"), else the person's words
        return s.name(found.get("family") or found["words"])
    if found.get("kind") == "category":
        return f"عائلة {s.name(found['name'])}"
    return None


def _of(v, s) -> str:
    found = subject(v, s)
    return f" من {found}" if found else ""


def _of_list(v, s) -> str:
    found = subject(v, s)
    return f" ({found})" if found else ""


def _sales(v, s) -> str:
    found = subject(v, s)
    return f"مبيعات {found}" if found else "المبيعات"


def _in(v, s, key: str = "branch") -> str:
    return f" في {s.name(v[key])}" if v.get(key) else ""


def _change(percent, s: Shown) -> str:
    if percent is None:
        return "بدون مبيعات قبل"
    if percent == 0:
        return "مستقرة"
    return f"{'ارتفاع' if percent > 0 else 'انخفاض'} {s.percent(percent)}"


def _count(value: int, s: Shown, one: str, two: str, few: str, many: str) -> str:
    if value == 1:
        return one
    if value == 2:
        return two
    return f"{s.number(value)} {few if 3 <= value <= 10 else many}"


def sales_of(v, s):
    worth = f"، بقيمة {s.money(v['money'])}" if "money" in v else ""
    return f"بيعت {s.pieces(v['pieces'])}{_of(v, s)}{_in(v, s)} {s.period(v['period'])} ({s.range(v['range'])}){worth}."


def best_sellers(v, s):
    text = (f"الأكثر مبيعا{_of_list(v, s)}{_in(v, s)} {s.period(v['period'])} هو {s.name(v['name'])}: "
            f"بيعت منه {s.pieces(v['pieces'])}.")
    others = [f"{s.name(row['name'])} ({s.number(row['pieces'])})" for row in v.get("next", [])]
    if others:
        text += f" بعده: {' و'.join(others)}."
    return text


def best_sellers_none(v, s):
    return f"لا مبيعات{_of_list(v, s)}{_in(v, s)} {s.period(v['period'])} ({s.range(v['range'])})."


def sales_vs_last(v, s):
    sales = f"{_sales(v, s)}{_in(v, s)}"
    now = f"{s.pieces(v['pieces'])} {s.period(v['period'])} ({s.range(v['range'])})"
    if v["percent"] is None:
        return f"{sales}: {now}، ولا شيء في الفترة السابقة ({s.range(v['before_range'])})."
    if v["percent"] == 0:
        return f"{sales} مستقرة: {now}، مثل الفترة السابقة ({s.range(v['before_range'])})."
    way = "ارتفعت" if v["percent"] > 0 else "انخفضت"
    return (f"{sales} {way} بنسبة {s.percent(v['percent'])}: {now}، "
            f"مقابل {s.number(v['before_pieces'])} قبل ({s.range(v['before_range'])}).")


def stock_of_part(v, s):
    if not v["pieces"]:
        return f"لم يبق أي مخزون{_of(v, s)}{_in(v, s)}."
    return f"بقيت {s.pieces(v['pieces'])}{_of(v, s)} في المخزون{_in(v, s)}."


def running_out(v, s):
    parts = _count(v["count"], s, "قطعة واحدة قد تنفد", "قطعتان قد تنفدان", "قطع قد تنفد", "قطعة قد تنفد")
    return (f"{parts}{_in(v, s)} خلال {s.days(v['days'])}{_of_list(v, s)}. "
            f"أولها: {s.name(v['name'])}، بقيت {s.pieces(v['pieces'])}، حوالي {s.days(v['days_left'])}.")


def running_out_none(v, s):
    return f"لا شيء{_of_list(v, s)} سينفد{_in(v, s)} خلال {s.days(v['days'])} القادمة."


def dead_stock(v, s):
    parts = _count(v["count"], s, "قطعة واحدة لم تُبع", "قطعتان لم تُباعا", "قطع لم تُبع", "قطعة لم تُبع")
    worth = f"، قيمتها {s.money(v['money'])} بسعر الشراء" if "money" in v else ""
    return f"{parts} منذ {s.days(v['days'])}{_of_list(v, s)}{_in(v, s)}: {s.pieces(v['pieces'])} على الرفوف{worth}."


def dead_stock_none(v, s):
    return f"كل المخزون{_of_list(v, s)}{_in(v, s)} بيع مرة واحدة على الأقل خلال آخر {s.days(v['days'])}."


def forecast(v, s):
    return (f"يُتوقع بيع حوالي {s.pieces(v['pieces'])}{_of(v, s)}{_in(v, s)} خلال {s.days(v['days'])} القادمة "
            f"(على الأرجح بين {s.number(v['low'])} و{s.number(v['high'])}).")


def forecast_none(v, s):
    return f"لا يوجد توقع بعد{_of_list(v, s)}. تُحسب التوقعات بعد استيراد المبيعات."


def what_to_order(v, s):
    lines = _count(v["count"], s, "سطر واحد", "سطران", "أسطر", "سطرا")
    cost = f"، بتكلفة {s.money(v['money'])}" if "money" in v else ""
    return (f"يجب طلب {s.pieces(v['pieces'])}{_of_list(v, s)}{_in(v, s)}، في {lines}{cost}. "
            f"هذا هو الاقتراح المحسوب يوم {s.day(v['made_on'])}.")


def what_to_order_none(v, s):
    return f"لم يبق شيء للطلب{_of_list(v, s)}{_in(v, s)} (اقتراح يوم {s.day(v['made_on'])})."


def what_to_order_no_run(v, s):
    return "لا يوجد اقتراح طلبية بعد. يمكن للمسير حسابه في صفحة الطلبيات."


def open_alerts(v, s):
    alerts = _count(v["count"], s, "تنبيه واحد مفتوح", "تنبيهان مفتوحان", "تنبيهات مفتوحة", "تنبيها مفتوحا")
    kind = ALERT_KINDS.get(v["alert"]["kind"], v["alert"]["kind"])
    return (f"{alerts}{_of_list(v, s)}{_in(v, s)}. الأحدث: {s.name(v['part'])} في "
            f"{s.name(v['alert_branch'])}، {kind}.")


def open_alerts_none(v, s):
    return f"لا توجد تنبيهات مفتوحة{_of_list(v, s)}{_in(v, s)}."


def late_deliveries(v, s):
    late = _count(v["count"], s, "توصيلة واحدة متأخرة", "توصيلتان متأخرتان", "توصيلات متأخرة", "توصيلة متأخرة")
    return (f"{late}. الأكثر تأخرا: الطلبية {s.name(v['order_number'])} من {s.name(v['supplier'])}، "
            f"متأخرة {s.days(v['days'])}.")


def late_deliveries_none(v, s):
    return "لا توجد توصيلات متأخرة من الموردين."


def today_briefing(v, s):
    text = _briefing_sales(v, s)
    needs, worth = v["needs_action"]["count"], v["worth_a_look"]["count"]
    text += f" تنبيهات تحتاجك: {s.number(needs)}، وتستحق نظرة: {s.number(worth)}."
    lines = v["to_order"]["lines"]
    text += f" للطلب: {s.number(lines)} سطرا." if lines else " لا شيء للطلب."
    late = v["late_deliveries"]["count"]
    text += f" توصيلات متأخرة: {s.number(late)}." if late else " لا توجد توصيلات متأخرة."
    running = v["running_out"]["count"]
    if running:
        text += f" قطع قد تنفد خلال {s.days(v['running_out']['within_days'])}: {s.number(running)}."
    return text


def _briefing_sales(v, s) -> str:
    if "sales_in_period" in v:
        period = v["sales_in_period"]
        return (f"{s.period(period['period'])} ({s.range(period['range'])}): بيعت {s.pieces(period['pieces'])}، "
                f"{_change(period['percent'], s)} مقارنة بالفترة السابقة ({s.number(period['before_pieces'])}). الآن:")
    week = v.get("sales_this_week")
    if not week:
        return "لا مبيعات بعد."
    if week["percent_vs_normal"] in (None, 0):
        compared = f"الأسبوع العادي {s.number(week['normal_week'])}"
    else:
        compared = f"{_change(week['percent_vs_normal'], s)} مقارنة بأسبوع عادي ({s.number(week['normal_week'])})"
    return f"هذا الأسبوع: بيعت {s.pieces(week['pieces'])}، {compared}."


def compare_branches(v, s):
    rows = v["branches"]
    when = f"{s.period(v['period'])} ({s.range(v['range'])})"
    if not rows or not rows[0]["pieces"]:
        return f"لا مبيعات{_of(v, s)} {when} في أي فرع."
    top, others = rows[0], rows[1:]
    text = f"{s.name(top['branch'])} يبيع أكثر{_of(v, s)}: {s.number(top['pieces'])} {when}"
    if others:
        listed = [f"{s.name(row['branch'])} ({s.number(row['pieces'])})" for row in others]
        text += f"، متقدما على {' و'.join(listed)}"
    changes = [f"{s.name(row['branch'])} {_change(row['percent_change'], s)}" for row in rows]
    return f"{text}. مقارنة بالفترة السابقة: {'، '.join(changes)}."


def explain_part_change(v, s):
    sales = f"{_sales(v, s)}{_in(v, s)}"
    numbers = f"{s.number(v['pieces_now'])} {s.period(v['period'])} مقابل {s.number(v['pieces_before'])} قبل"
    if v["direction"] == "same":
        return f"{sales} لم تتغير تقريبا: {numbers}."
    head = f"{sales} {_way(v, s)}: {numbers}."
    reasons = v["reasons"]
    if not reasons:
        return f"{head} لا أرى سببا واضحا في البيانات: لا المخزون ولا الأسعار ولا التنبيهات ولا السنة الماضية تفسر ذلك."
    text = f"{head} السبب الرئيسي: {_reason(reasons[0], v, s)}."
    if len(reasons) > 1:
        text += f" وأيضا: {_reason(reasons[1], v, s)}."
    return text


def _way(v, s) -> str:
    way = "انخفضت" if v["direction"] == "down" else "ارتفعت"
    if v["percent_change"] is None:
        return way
    if abs(v["percent_change"]) < SMALL_CHANGE_PERCENT:
        return f"{way} قليلا ({s.percent(v['percent_change'])})"
    return f"{way} بنسبة {s.percent(v['percent_change'])}"


def _reason(reason: dict, v, s) -> str:
    over = {"parts_and_branches": " (في المجموع، كل هذه القطع وكل الفروع)", "branches": " (في المجموع، كل الفروع)"}
    counted = over.get(v.get("days_out_of_stock_counts"), "")
    kind = reason["kind"]
    if kind == "out_of_stock":
        return (f"نفاد المخزون {s.days(reason['days_now'])} {s.period(v['period'])}{counted}، "
                f"مقابل {s.number(reason['days_before'])} قبل")
    if kind == "back_in_stock":
        return f"عاد المخزون: نفد {s.days(reason['days_before'])} قبل{counted}، و{s.number(reason['days_now'])} فقط الآن"
    if kind in ("price_up", "price_down"):
        prices = f" (من {s.money(reason['price_before'])} إلى {s.money(reason['price_now'])})" if "price_now" in reason else ""
        return f"{'ارتفع' if kind == 'price_up' else 'انخفض'} متوسط السعر بنسبة {s.percent(reason['percent'])}{prices}"
    if kind == "season":
        return f"هذا عادي في هذا الموسم، نفس الأيام في السنة الماضية بيعت {s.number(reason['last_year'])}"
    return f"تنبيه مفتوح في {s.name(reason['branch'])}: {ALERT_KINDS.get(reason['alert_kind'], reason['alert_kind'])}"


def part_details(v, s):
    totals = v["totals"]
    best = v["parts"][0]
    text = (f"{subject(v, s) or 'هذه القطع'}{_in(v, s)}: {s.pieces(totals['stock_total'])} في المخزون، "
            f"بيعت {s.number(totals['sold_last_30_days'])} في آخر 30 يوما، "
            f"ويُتوقع بيع حوالي {s.number(totals['expected_next_30_days'])} في الـ30 يوما القادمة.")
    if v["matches"] > 1:
        text += f" {s.number(v['matches'])} قطع مطابقة؛ الأكثر مبيعا {s.name(best['name'])}."
    return text


def part_not_found(v, s):
    return f"لم أجد أي قطعة باسم «{s.name(v['part'])}». جرّب اسمها أو رقمها."


def not_sure(v, s):
    by = f" بـ«{s.name(v['words'])}»" if v.get("words") else ""
    return "لست متأكدا مما تقصد{by}. هل تقصد أحد هذه الأسئلة؟".format(by=by)
