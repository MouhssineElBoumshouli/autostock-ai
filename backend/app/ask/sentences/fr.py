"""Réponses en français. Chacune commence par le fait le plus important, en phrases courtes et simples."""

from app.ask.sentences.shown import Shown
from app.ask.why import SMALL_CHANGE_PERCENT

FIXED = {
    "refusal": "Je ne peux pas faire ça. Je lis seulement le stock, les ventes, les alertes, les commandes et les "
               "fournisseurs du magasin : je ne change jamais les données, je ne passe pas de commande, et je ne sais "
               "rien des clients ni du personnel.",
    "not_understood": "Je n’ai pas compris la question. Essayez de la poser autrement, par exemple « stock des plaquettes à Rabat ».",
    "cannot_answer": "Je ne sais pas encore répondre à cette question.",
    "which_part_stock": "Quelle pièce ? Par exemple : « donne-moi tout sur l’alternateur ».",
    "which_part_forecast": "Quelle pièce ? Par exemple : « combien de plaquettes de frein on va vendre ».",
}
ALERT_KINDS = {
    "sales_spike": "ventes bien plus fortes que d’habitude", "sales_drop": "ventes bien plus faibles que d’habitude",
    "sold_at_zero": "vendu alors que le stock était à 0", "stock_frozen": "stock qui ne bouge pas",
    "negative_stock": "stock négatif",
}


def subject(v: dict, s: Shown) -> str | None:
    """« Filtre à huile - Dacia Logan », « la famille Freinage », « filtres à huile » ; None pour tout le magasin."""
    found = v.get("subject") or {}
    if found.get("kind") == "part":
        return s.name(found["name"])
    if found.get("kind") == "matching":  # the person's own words: "filtres à huile"
        return s.name(found["words"])
    if found.get("kind") == "category":
        return f"la famille {s.name(found['name'])}"
    return None


def _of(v, s) -> str:
    """« de Filtre à huile », « d’amortisseurs », « de la famille Freinage »."""
    found = subject(v, s)
    return f" {de(found)}" if found else ""


def de(text: str) -> str:
    """« de batteries », « d’huile »."""
    return f"d’{text}" if text[:1].lower() in "aeiouyéèêàâîôûh" else f"de {text}"


def _of_list(v, s) -> str:
    found = subject(v, s)
    return f" ({found})" if found else ""


def _in(v, s, key: str = "branch") -> str:
    return f" à {s.name(v[key])}" if v.get(key) else ""


def _change(percent, s: Shown) -> str:
    if percent is None:
        return "aucune vente avant"
    if percent == 0:
        return "stable"
    return f"{'en hausse de' if percent > 0 else 'en baisse de'} {s.percent(percent)}"


def sales_of(v, s):
    worth = f", pour {s.money(v['money'])}" if "money" in v else ""
    return f"{s.pieces(v['pieces'])}{_of(v, s)} vendues{_in(v, s)} {s.period(v['period'])} ({s.range(v['range'])}){worth}."


def best_sellers(v, s):
    text = (f"La meilleure vente{_of(v, s)}{_in(v, s)} {s.period(v['period'])} est {s.name(v['name'])} : "
            f"{s.pieces(v['pieces'])} vendues.")
    others = [f"{s.name(row['name'])} ({s.number(row['pieces'])})" for row in v.get("next", [])]
    if others:
        text += f" Ensuite : {' et '.join(others)}."
    return text


def best_sellers_none(v, s):
    return f"Aucune vente{_of(v, s)}{_in(v, s)} {s.period(v['period'])} ({s.range(v['range'])})."


def sales_vs_last(v, s):
    sales = f"Les ventes{_of(v, s)}{_in(v, s)}"
    now = f"{s.pieces(v['pieces'])} {s.period(v['period'])} ({s.range(v['range'])})"
    if v["percent"] is None:
        return f"{sales} : {now}, et aucune sur la période d’avant ({s.range(v['before_range'])})."
    if v["percent"] == 0:
        return f"{sales} sont stables : {now}, autant qu’avant ({s.range(v['before_range'])})."
    way = "en hausse" if v["percent"] > 0 else "en baisse"
    return (f"{sales} sont {way} de {s.percent(v['percent'])} : {now}, "
            f"contre {s.number(v['before_pieces'])} avant ({s.range(v['before_range'])}).")


def stock_of_part(v, s):
    if not v["pieces"]:
        return f"Plus aucun stock{_of(v, s)}{_in(v, s)}."
    return f"Il reste {s.pieces(v['pieces'])}{_of(v, s)} en stock{_in(v, s)}."


def running_out(v, s):
    parts = "1 pièce risque" if v["count"] == 1 else f"{s.number(v['count'])} pièces risquent"
    return (f"{parts} d’être en rupture{_in(v, s)} d’ici {s.days(v['days'])}{_of_list(v, s)}. "
            f"La première : {s.name(v['name'])}, {s.pieces(v['pieces'])} restantes, environ {s.days(v['days_left'])}.")


def running_out_none(v, s):
    return f"Aucune rupture prévue{_of_list(v, s)}{_in(v, s)} dans les {s.days(v['days'])} à venir."


def dead_stock(v, s):
    parts = "1 pièce ne s’est pas vendue" if v["count"] == 1 else f"{s.number(v['count'])} pièces ne se sont pas vendues"
    worth = f", pour {s.money(v['money'])} au prix d’achat" if "money" in v else ""
    return f"{parts} depuis {s.days(v['days'])}{_of_list(v, s)}{_in(v, s)} : {s.pieces(v['pieces'])} en rayon{worth}."


def dead_stock_none(v, s):
    return f"Tout le stock{_of_list(v, s)}{_in(v, s)} s’est vendu au moins une fois ces {s.days(v['days'])}."


def forecast(v, s):
    return (f"Environ {s.pieces(v['pieces'])}{_of(v, s)} devraient se vendre{_in(v, s)} dans les {s.days(v['days'])} à venir "
            f"(probablement entre {s.number(v['low'])} et {s.number(v['high'])}).")


def forecast_none(v, s):
    return f"Pas encore de prévision{_of_list(v, s)}. Les prévisions sont calculées après l’import des ventes."


def what_to_order(v, s):
    lines = "1 ligne" if v["count"] == 1 else f"{s.number(v['count'])} lignes"
    cost = f", pour {s.money(v['money'])}" if "money" in v else ""
    return (f"À commander{_of_list(v, s)}{_in(v, s)} : {s.pieces(v['pieces'])}, en {lines}{cost} "
            f"(proposition du {s.day(v['made_on'])}).")


def what_to_order_none(v, s):
    return f"Plus rien à commander{_of_list(v, s)}{_in(v, s)} (proposition du {s.day(v['made_on'])})."


def what_to_order_no_run(v, s):
    return "Pas encore de proposition de commande. Un gérant peut la calculer dans À commander."


def open_alerts(v, s):
    alerts = "1 alerte ouverte" if v["count"] == 1 else f"{s.number(v['count'])} alertes ouvertes"
    kind = ALERT_KINDS.get(v["alert"]["kind"], v["alert"]["kind"])
    return (f"{alerts}{_of_list(v, s)}{_in(v, s)}. La plus récente : {s.name(v['part'])} à "
            f"{s.name(v['alert_branch'])}, {kind}.")


def open_alerts_none(v, s):
    return f"Aucune alerte ouverte{_of_list(v, s)}{_in(v, s)}."


def late_deliveries(v, s):
    late = "1 livraison est en retard" if v["count"] == 1 else f"{s.number(v['count'])} livraisons sont en retard"
    return (f"{late}. La plus en retard : la commande {s.name(v['order_number'])} de {s.name(v['supplier'])}, "
            f"{s.days(v['days'])} de retard.")


def late_deliveries_none(v, s):
    return "Aucune livraison fournisseur en retard."


def today_briefing(v, s):
    text = _briefing_sales(v, s)
    needs, worth = v["needs_action"]["count"], v["worth_a_look"]["count"]
    text += f" {s.number(needs)} alertes à traiter, {s.number(worth)} à surveiller."
    lines = v["to_order"]["lines"]
    text += f" À commander : {s.number(lines)} lignes." if lines else " Rien à commander."
    late = v["late_deliveries"]["count"]
    text += f" {s.number(late)} livraisons en retard." if late else " Aucune livraison en retard."
    running = v["running_out"]["count"]
    if running:
        text += f" {s.number(running)} pièces risquent la rupture d’ici {s.days(v['running_out']['within_days'])}."
    return text


def _briefing_sales(v, s) -> str:
    if "sales_in_period" in v:
        period = v["sales_in_period"]
        when = s.period(period["period"])
        return (f"{when[:1].upper()}{when[1:]} ({s.range(period['range'])}) : {s.pieces(period['pieces'])} vendues, "
                f"{_change(period['percent'], s)} par rapport à la période d’avant ({s.number(period['before_pieces'])}). "
                f"En ce moment :")
    week = v.get("sales_this_week")
    if not week:
        return "Pas encore de ventes."
    if week["percent_vs_normal"] in (None, 0):
        compared = f"une semaine normale c’est {s.number(week['normal_week'])}"
    else:
        compared = f"{_change(week['percent_vs_normal'], s)} par rapport à une semaine normale ({s.number(week['normal_week'])})"
    return f"Cette semaine : {s.pieces(week['pieces'])} vendues, {compared}."


def compare_branches(v, s):
    rows = v["branches"]
    when = f"{s.period(v['period'])} ({s.range(v['range'])})"
    if not rows or not rows[0]["pieces"]:
        return f"Aucune vente{_of(v, s)} {when}, dans aucune agence."
    top, others = rows[0], rows[1:]
    what = f" {de(subject(v, s))}" if subject(v, s) else ""
    text = f"{s.name(top['branch'])} vend le plus{what} : {s.number(top['pieces'])} {when}"
    if others:
        listed = [f"{s.name(row['branch'])} ({s.number(row['pieces'])})" for row in others]
        text += f", devant {', '.join(listed[:-1]) + ' et ' + listed[-1] if len(listed) > 1 else listed[0]}"
    changes = [f"{s.name(row['branch'])} {_change(row['percent_change'], s)}" for row in rows]
    return f"{text}. Par rapport à la période d’avant : {', '.join(changes)}."


def explain_part_change(v, s):
    sales = f"Les ventes{_of(v, s)}{_in(v, s)}"
    numbers = f"{s.number(v['pieces_now'])} {s.period(v['period'])} contre {s.number(v['pieces_before'])} avant"
    if v["direction"] == "same":
        return f"{sales} n’ont presque pas changé : {numbers}."
    head = f"{sales} sont {_way(v, s)} : {numbers}."
    reasons = v["reasons"]
    if not reasons:
        return (f"{head} Je ne vois pas de raison claire dans les données : ni le stock, ni les prix, ni les "
                f"alertes, ni l’an dernier ne l’expliquent.")
    first = reasons[0]
    text = f"{head} Raison principale : {_reason(first, v, s)}."
    if len(reasons) > 1:
        text += f" Aussi : {_reason(reasons[1], v, s)}."
    return text


def _way(v, s) -> str:
    """« en baisse de 12 % », ou « un peu en baisse (4 %) » pour un petit changement."""
    way = "en baisse" if v["direction"] == "down" else "en hausse"
    if v["percent_change"] is None:
        return way
    if abs(v["percent_change"]) < SMALL_CHANGE_PERCENT:
        return f"un peu {way} ({s.percent(v['percent_change'])})"
    return f"{way} de {s.percent(v['percent_change'])}"


def _reason(reason: dict, v, s) -> str:
    over = {"parts_and_branches": " (additionnés sur les pièces et les agences)", "branches": " (additionnés sur les agences)"}
    counted = over.get(v.get("days_out_of_stock_counts"), "")
    kind = reason["kind"]
    if kind == "out_of_stock":
        return (f"rupture de stock {s.days(reason['days_now'])} {s.period(v['period'])}{counted}, "
                f"contre {s.number(reason['days_before'])} avant")
    if kind == "back_in_stock":
        return (f"de nouveau en stock : {s.days(reason['days_before'])} de rupture avant{counted}, "
                f"seulement {s.number(reason['days_now'])} maintenant")
    if kind in ("price_up", "price_down"):
        prices = f" ({s.money(reason['price_before'])} à {s.money(reason['price_now'])})" if "price_now" in reason else ""
        return f"le prix moyen a {'augmenté' if kind == 'price_up' else 'baissé'} de {s.percent(reason['percent'])}{prices}"
    if kind == "season":
        return f"c’est normal pour la saison, les mêmes jours l’an dernier : {s.number(reason['last_year'])} vendues"
    return f"une alerte ouverte à {s.name(reason['branch'])} : {ALERT_KINDS.get(reason['alert_kind'], reason['alert_kind'])}"


def part_details(v, s):
    totals = v["totals"]
    best = v["parts"][0]
    text = (f"{_capital(subject(v, s)) or 'Ces pièces'}{_in(v, s)} : {s.pieces(totals['stock_total'])} en stock, "
            f"{s.number(totals['sold_last_30_days'])} vendues ces 30 derniers jours, "
            f"environ {s.number(totals['expected_next_30_days'])} attendues dans les 30 prochains jours.")
    if v["matches"] > 1:
        text += f" {s.number(v['matches'])} pièces correspondent ; la plus vendue est {s.name(best['name'])}."
    return text


def _capital(text: str | None) -> str | None:
    return text[:1].upper() + text[1:] if text else text


def part_not_found(v, s):
    return f"Je n’ai trouvé aucune pièce appelée « {s.name(v['part'])} ». Essayez sa désignation ou sa référence."


def not_sure(v, s):
    by = f" « {s.name(v['words'])} »" if v.get("words") else ""
    return "Je ne suis pas sûr de comprendre{by}. Vouliez-vous dire une de ces questions ?".format(by=by)
