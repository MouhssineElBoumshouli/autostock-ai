"""Ask your shop: checking what the model returns, the keyword rule, words and periods. No database."""

from datetime import date

import pytest

from app.ai import llm
from app.ask import model_reader
from app.ask.keyword_rule import read_with_rule
from app.ask.model_reader import read_with_model
from app.ask.periods import day_range, range_before
from app.ask.question import CANNOT_ANSWER, NOT_SURE, Question, ShopWords, checked_question
from app.ask.understood_line import understood_line
from app.ask.words import content_key, normalize, same_word, vocabulary

SHOP = ShopWords(
    categories=("Brakes", "Filters", "Lighting"),
    branches=("Casablanca - Maarif", "Rabat - Agdal"),
    part_words=vocabulary(["Oil filter Bosch", "Brake pads front", "Brake disc", "disque de frein", "plaquettes de frein", "مضخة الماء"]),
)


# Checking the model's JSON

def test_a_known_type_with_allowed_filters_is_accepted():
    raw = {"type": "sales_of", "part": " oil filter ", "category": None, "branch": "Rabat - Agdal", "period": "this_week"}
    assert checked_question(raw, SHOP) == Question("sales_of", part="oil filter", branch="Rabat - Agdal", period="this_week")


@pytest.mark.parametrize("raw", [
    "sales_of",  # not an object
    {"type": "delete_parts"},  # unknown type
    {"type": "sales_of", "sql": "DROP TABLE parts"},  # unknown key
    {"type": "late_deliveries", "part": "oil filter"},  # filter this type doesn't take
    {"type": "sales_of", "category": "Tyres"},  # not a category of this shop
    {"type": "sales_of", "branch": "Other Shop"},  # not a branch of this shop
    {"type": "sales_of", "period": "next_decade"},
    {"type": "sales_of", "part": 42},
    {"type": "sales_of", "part": "x" * 81},
    {"type": "sales_of", "part": "null"},
])
def test_anything_not_allowed_is_rejected(raw):
    assert checked_question(raw, SHOP) is None


def test_model_answer_is_checked_and_unused_filters_dropped(monkeypatch):
    monkeypatch.setattr(llm, "ask_json", lambda *_: {
        "type": "what_to_order", "part": "pads", "category": "Brakes", "branch": None, "period": "today",
    })
    assert read_with_model("what to order for brakes", SHOP) == Question("what_to_order", category="Brakes")


@pytest.mark.parametrize("reply", [None, "not json", {"type": "sales_of", "branch": "Paris"}, {"type": "sing_a_song"}])
def test_a_bad_or_missing_model_answer_gives_none(monkeypatch, reply):
    monkeypatch.setattr(llm, "ask_json", lambda *_: reply)
    assert read_with_model("anything", SHOP) is None


def test_model_is_only_offered_the_shop_names_and_allowed_values():
    schema = model_reader.schema_for(SHOP)
    assert schema["properties"]["branch"]["enum"] == ["Casablanca - Maarif", "Rabat - Agdal", None]
    assert "cannot_answer" in schema["properties"]["type"]["enum"]


def test_llm_is_off_without_an_address(monkeypatch):
    monkeypatch.setattr(llm, "OLLAMA_URL", "")
    assert llm.is_on() is False
    assert llm.ask_json("x", "y", {}) is None


def test_llm_is_off_when_ollama_does_not_answer(monkeypatch):
    monkeypatch.setattr(llm, "OLLAMA_URL", "http://127.0.0.1:9")  # nothing listens there
    assert llm.is_on() is False
    assert llm.ask_json("x", "y", {}) is None


# The keyword rule

@pytest.mark.parametrize("text, expected", [
    ("how many oil filters did we sell last month", Question("sales_of", part="oil filters", period="last_month")),
    ("ventes freinage à Rabat cette semaine", Question("sales_of", category="Brakes", branch="Rabat - Agdal", period="this_week")),
    ("best sellers in casa", Question("best_sellers", branch="Casablanca - Maarif")),
    ("شنو غادي يسالي", Question("running_out")),
    ("what to order for filters", Question("what_to_order", category="Filters")),
    ("stok plaquettes", Question("stock_of_part", part="plaquettes")),
    ("المخزون الراكد", Question("dead_stock")),
    ("what is not moving", Question("dead_stock")),
    ("ne se vend pas", Question("dead_stock")),
    ("ma kaytba3ch", Question("dead_stock")),
    ("alerts in rabat", Question("open_alerts", branch="Rabat - Agdal")),
    ("livraisons en retard", Question("late_deliveries")),
    ("forecast brake discs", Question("forecast_of_part", part="brake discs")),
    ("sales this month compared to last month", Question("sales_vs_last", period="this_month")),
    ("sales compared to last week", Question("sales_vs_last", period="this_week")),
    ("what sold the most last month in rabat", Question("best_sellers", branch="Rabat - Agdal", period="last_month")),
    ("total sales yesterday", Question("sales_of", period="yesterday")),
    ("il reste combien de disques de frein a rabat", Question("stock_of_part", part="disques frein", branch="Rabat - Agdal")),
    ("كم لدينا من مضخة الماء في الرباط", Question("stock_of_part", part="مضخه الماء", branch="Rabat - Agdal")),
    ("ventes freinage de l'année", Question("sales_of", category="Brakes", period="this_year")),
    ("faut commander quoi pour l'éclairage", Question("what_to_order", category="Lighting")),
    ("مبيعات هذا الشهر", Question("sales_of", period="this_month")),
    ("chhal bi3na had chhar", Question("sales_of", period="this_month")),
])
def test_rule_reads_each_question_type(text, expected):
    assert read_with_rule(text, SHOP) == expected


@pytest.mark.parametrize("text", ["who is our best customer", "change the price of oil filters", "print an invoice"])
def test_rule_says_what_it_cannot_answer(text):
    assert read_with_rule(text, SHOP) == CANNOT_ANSWER


def test_words_the_rule_does_not_know_are_never_made_a_part_name():
    question = read_with_rule("stock of unicorn horns in rabat", SHOP)
    assert question.type == NOT_SURE
    assert question.part == "unicorn horns" and question.branch == "Rabat - Agdal"
    assert question.suggestions[0] == "stock_of_part" and len(question.suggestions) == 3


@pytest.mark.parametrize("text", ["bonjour", "", "brake pads"])
def test_no_question_type_means_not_sure_not_a_guess(text):
    question = read_with_rule(text, SHOP)
    assert question.type == NOT_SURE
    assert 2 <= len(question.suggestions) <= 3


def test_every_answerable_reading_is_shown_in_plain_words():
    assert understood_line(Question("sales_of", part="brake pads", branch="Rabat - Agdal", period="last_month")) == (
        "I understood: Sales of brake pads · Rabat - Agdal · last month"
    )
    assert understood_line(Question("best_sellers", category="Filters")) == (
        "I understood: Best sellers in Filters (category) · the last 30 days"
    )
    assert understood_line(Question("sales_vs_last")) == "I understood: Sales compared with the period before · this week"
    assert understood_line(Question("late_deliveries")) == "I understood: Late deliveries"
    assert understood_line(CANNOT_ANSWER) is None
    assert understood_line(Question(NOT_SURE, suggestions=("sales_of",))) is None


# Words and periods

def test_words_are_compared_without_accents_case_or_arabic_spelling_differences():
    assert normalize("Électrique, ÇA!") == "electrique ca"
    assert normalize("الأكثر مبيعاً") == normalize("الاكثر مبيعا")
    assert content_key("les filtres à huile") == content_key("Filtres huile")
    assert content_key("الفرامل") == content_key("فرامل")
    assert same_word("plaquete", "plaquette") and not same_word("sel", "sell")
    assert same_word("stok", "stock") and not same_word("most", "mort")
    assert same_word("batteries", "battery") is False and same_word(normalize("بطاريات"), normalize("البطارية"))


TODAY = date(2026, 10, 20)


@pytest.mark.parametrize("period, expected", [
    ("today", (date(2026, 10, 20), date(2026, 10, 20))),
    ("yesterday", (date(2026, 10, 19), date(2026, 10, 19))),
    ("this_week", (date(2026, 10, 14), date(2026, 10, 20))),
    ("last_week", (date(2026, 10, 7), date(2026, 10, 13))),
    ("this_month", (date(2026, 10, 1), date(2026, 10, 20))),
    ("last_month", (date(2026, 9, 1), date(2026, 9, 30))),
    ("this_year", (date(2026, 1, 1), date(2026, 10, 20))),
    ("last_30_days", (date(2026, 9, 21), date(2026, 10, 20))),
])
def test_periods_end_on_the_shop_today(period, expected):
    assert day_range(period, TODAY) == expected


@pytest.mark.parametrize("period, today, expected", [
    ("this_week", TODAY, (date(2026, 10, 7), date(2026, 10, 13))),
    ("this_month", TODAY, (date(2026, 9, 1), date(2026, 9, 20))),  # same number of days
    ("this_month", date(2026, 3, 31), (date(2026, 2, 1), date(2026, 2, 28))),  # cut at the shorter month's end
    ("last_month", TODAY, (date(2026, 8, 1), date(2026, 8, 31))),
    ("this_year", date(2028, 2, 29), (date(2027, 1, 1), date(2027, 2, 28))),
])
def test_the_period_before_is_the_same_length(period, today, expected):
    assert range_before(period, today) == expected
