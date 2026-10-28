"""The app's own answers (app/ask/sentences/): the most important fact first, numbers written the way
each language writes them, in the question's language, never calling one thing another ("to order" is
never "sold"). Also: why sales changed, worked out by rules (app/ask/why.py), and which language to
answer in (app/ask/reply_language.py).
"""

import pytest

from app.ask.answer_parts import Answer, family_name
from app.ask.reply_language import reply_language
from app.ask.sentences import LANGUAGES, written_answer
from app.ask.sentences.shown import Shown
from app.ask.why import SalesFacts, direction, reasons

PART = {"kind": "part", "name": "Battery 70Ah"}
BRANCHES = [
    {"branch": "Casablanca - Maarif", "pieces": 181, "pieces_before": 150, "percent_change": 21},
    {"branch": "Rabat - Agdal", "pieces": 125, "pieces_before": 125, "percent_change": 0},
    {"branch": "Marrakech - Gueliz", "pieces": 107, "pieces_before": 120, "percent_change": -11},
]
EXPLAIN = {
    "subject": {"kind": "matching", "words": "filtres à huile"}, "period": "this_month", "pieces_now": 3183,
    "pieces_before": 3346, "percent_change": -5, "direction": "down", "days_out_of_stock_counts": "branches",
    "reasons": [{"kind": "out_of_stock", "days_now": 13, "days_before": 5}],
}


def write(key: str, values: dict, language: str = "en", currency: str | None = "MAD") -> str:
    return written_answer(Answer(key, values, "English sentence"), language, currency)


def test_compare_branches_leads_with_the_winner_then_the_others():
    values = {"subject": PART, "period": "this_month", "range": "2026-10-01/2026-10-28", "branches": BRANCHES}
    assert write("compare_branches", values, "fr").startswith(
        "Casablanca - Maarif vend le plus de Battery 70Ah : 181 ce mois-ci (1 oct. – 28 oct.), "
        "devant Rabat - Agdal (125) et Marrakech - Gueliz (107).")
    assert write("compare_branches", values, "en").startswith("Casablanca - Maarif sells the most of Battery 70Ah: 181 pieces")


def test_why_states_the_main_reason_first():
    assert write("explain_part_change", EXPLAIN, "fr") == (
        "Les ventes de filtres à huile sont un peu en baisse (5 %) : 3 183 ce mois-ci contre 3 346 avant. "
        "Raison principale : rupture de stock 13 jours ce mois-ci (additionnés sur les agences), contre 5 avant.")


def test_why_says_so_honestly_when_no_reason_fits():
    text = write("explain_part_change", {**EXPLAIN, "percent_change": -30, "reasons": []})
    assert text.startswith("Sales of filtres à huile are down 30%") and "I see no clear reason in the data" in text


def test_what_to_order_is_never_called_sold():
    values = {"subject": {"kind": "all"}, "count": 222, "pieces": 4662, "money": 121227400, "made_on": "2026-10-21T08:00:00"}
    english = write("what_to_order", values)
    assert english.startswith("You should order 4,662 pieces, in 222 lines, costing MAD 1,212,274.")
    assert "sold" not in english and "vend" not in write("what_to_order", values, "fr")


def test_people_who_dont_see_money_get_no_money_words():
    values = {"subject": {"kind": "all"}, "count": 2, "pieces": 10, "made_on": "2026-10-21"}  # no "money" for staff
    assert "MAD" not in write("what_to_order", values, currency=None) and "DH" not in write("what_to_order", values, "fr", None)


@pytest.mark.parametrize(("language", "number", "money"), [
    ("en", "4,662", "MAD 12,340"), ("fr", "4 662", "12 340 DH"), ("ar", "⁦4 662⁩", "⁦12 340 DH⁩"),
])
def test_numbers_and_money_are_written_the_way_each_language_writes_them(language, number, money):
    shown = Shown(language, "MAD")
    assert shown.number(4662) == number and shown.money(1234000) == money


@pytest.mark.parametrize(("count", "pieces"), [(1, "قطعة واحدة"), (2, "قطعتان"), (5, "⁦5⁩ قطع"), (40, "⁦40⁩ قطعة")])
def test_arabic_counts_pieces_the_arabic_way(count, pieces):
    assert Shown("ar", None).pieces(count) == pieces


def test_every_answer_has_a_sentence_in_every_language():
    keys = {name for name, value in vars(LANGUAGES["en"]).items() if callable(value) and not name.startswith("_")}
    for language, sentences in LANGUAGES.items():
        missing = {key for key in keys if not callable(getattr(sentences, key, None))}
        assert missing <= {"subject", "Shown"}, (language, missing)
        assert set(sentences.FIXED) == set(LANGUAGES["en"].FIXED), language


# Why: rules, not guesses

def facts(**changes) -> SalesFacts:
    base = dict(now=80, before=100, last_year=0, out_now=0, out_before=0, price_now=None, price_before=None)
    return SalesFacts(**{**base, **changes})


def test_more_days_out_of_stock_is_the_main_reason_for_a_drop():
    assert reasons(facts(out_now=13, out_before=5))[0] == {"kind": "out_of_stock", "days_now": 13, "days_before": 5}


def test_a_price_rise_explains_a_drop():
    assert reasons(facts(price_now=11000, price_before=10000))[0]["kind"] == "price_up"


def test_last_years_same_days_explain_a_seasonal_change():
    assert reasons(facts(last_year=82)) == [{"kind": "season", "last_year": 82}]


def test_an_open_drop_alert_explains_a_drop_but_a_spike_alert_does_not():
    assert reasons(facts(alerts=({"kind": "sales_drop", "branch": "Rabat - Agdal"},)))[0]["kind"] == "alert"
    assert reasons(facts(alerts=({"kind": "sales_spike", "branch": "Rabat - Agdal"},))) == []


def test_a_rise_after_stock_outs_is_back_in_stock():
    assert reasons(facts(now=120, out_now=2, out_before=9))[0]["kind"] == "back_in_stock"


def test_no_reason_found_means_none_is_made_up():
    assert reasons(facts()) == []
    assert direction(101, 100) == "same" and direction(80, 100) == "down"


# Which language to answer in

@pytest.mark.parametrize(("question", "language"), [
    ("Why are brake pad sales down?", "en"),
    ("Et le mois dernier ?", "fr"),
    ("Supprime toutes les alertes", "fr"),
    ("ما الجديد اليوم؟", "ar"),
    ("3lach tay7 lbi3 dyal les plaquettes?", "ar"),  # Darija in Latin letters: answered in Arabic
    ("chno khassni nkhaf mno?", "ar"),
    ("stock ?", "fr"),  # too short to tell: the person's app language
])
def test_answers_are_in_the_questions_language(question, language):
    assert reply_language(question, "fr") == language


def test_a_group_of_parts_is_named_by_the_shops_own_family_name():
    assert family_name(["Oil filter - Kia Picanto 1.0", "Oil filter - VW Golf 7"]) == "Oil filter"
    assert family_name(["Oil filter - Kia Picanto 1.0", "Air filter - Kia Picanto 1.0"]) is None
    values = {"subject": {"kind": "matching", "words": "plaquettes frein", "family": "Brake pads front"}, "pieces": 1542,
              "branch": "Rabat - Agdal"}
    assert write("stock_of_part", values, "fr") == "Il reste 1 542 pièces de Brake pads front en stock à Rabat - Agdal."
