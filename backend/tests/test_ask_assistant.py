"""The "Ask your shop" assistant without the online assistant (Groq off, offline or out of allowance):
the app reads the question (rule, follow-up, or the local model as strict JSON), runs one read-only lookup
and writes the answer itself (tests/test_ask_sentences.py). Also: money hidden from staff, each shop sees
only its own data. The online assistant is tested in tests/test_online_assistant.py.

The local model is a scripted fake here: these tests check the app around it
(the reading is measured by app/ask/check_assistant.py on the 60 open questions).
"""

import copy
import json
import re
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from sqlalchemy import update

from app.ai import llm
from app.ask import model_reader
from app.ask.keyword_rule import read_follow_up, read_with_rule
from app.ask.answer_parts import Answer
from app.ask.number_check import numbers_in_words, numbers_written
from app.ask.question import Question, ShopWords, checked_question
from app.ask.tools import look_up
from app.db import SessionLocal
from app.models import AuditLog, Branch, Organization, StockOut
from tests.helpers import OWNER_PASSWORD, create_other_shop, logged_in_browser
from tests.test_ask import (  # noqa: F401  (shop and several_brake_pads_shop are fixtures)
    LAST_DAY, MAIN, RABAT, branch_named, new_part, select_part, sell, shelve, several_brake_pads_shop, shop,
    staff_browser,
)
from tests.test_today import add_alert

CASA = "Casablanca - Maarif"
SHOP = ShopWords(categories=("Brakes", "Oils"), branches=(CASA, RABAT), part_words=frozenset(
    {"brake", "pads", "oil", "filter", "filters", "plaquettes"}))
NOTHING = {"part": None, "category": None, "branch": None, "period": None, "branches": None}


class FakeModel:
    """The local model's readings, scripted; remembers what it was sent."""

    def __init__(self, readings: list[object]):
        self.readings = list(readings)
        self.reads: list[dict] = []

    def ask_json(self, instructions, text, schema, model=None):
        self.reads.append({"instructions": instructions, "text": text, "schema": schema})
        return self.readings.pop(0)


@pytest.fixture
def model(monkeypatch):
    """model(readings=[json, ...]) installs the fake local model and returns it (no Groq key in tests)."""
    monkeypatch.setattr(llm, "is_on", lambda model=None: True)

    def install(readings=()):
        fake = FakeModel(list(readings))
        monkeypatch.setattr(llm, "ask_json", fake.ask_json)
        return fake

    return install


def chat(browser, question: str, previous: dict | None = None, status: int = 200) -> list[dict]:
    response = browser.post("/api/ask/chat", json={"question": question, "previous": previous})
    assert response.status_code == status, response.text
    if status != 200:
        return []
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in response.text.splitlines() if line]


def done(events: list[dict]) -> dict:
    assert events[-1]["type"] == "done"
    return events[-1]


def shown(events: list[dict]) -> str:
    return "".join(event["text"] for event in events if event["type"] == "text")


# Read, look up, write


@pytest.mark.parametrize("question", ["What's going on today?", "Quoi de neuf ?", "ach kayn lyoum?", "how is the shop doing this week?"])
def test_broad_questions_get_todays_briefing(browser, shop, model, question):
    model()
    assert done(chat(browser, question))["question"]["type"] == "today_briefing"


def test_the_model_reads_what_the_rule_is_unsure_about_as_strict_json(browser, shop, model):
    fake = model(readings=[{**NOTHING, "type": "sales_of", "part": "oil filters", "period": "this_week"}])
    result = done(chat(browser, "chhal tba3 mn filtre a huile had simana wlla la?"))
    assert result["read_by"] == "model" and result["question"]["type"] == "sales_of"
    schema = fake.reads[0]["schema"]
    assert set(schema["properties"]["type"]["enum"]) >= {"today_briefing", "compare_branches", "explain_part_change",
                                                          "part_details", "cannot_answer"}
    assert schema["properties"]["branch"]["enum"][-1] is None
    assert "same" not in schema["properties"]["type"]["enum"], "no question before: nothing to follow up on"


def test_a_reading_that_isnt_allowed_means_not_understood(browser, shop, model):
    fake = model(readings=[{**NOTHING, "type": "sales_of", "branch": "Tangier"}])
    result = done(chat(browser, "zzz qqq"))
    assert result["question"] is None and result["lookups"] == [] and result["written_by"] == "app"
    assert len(fake.reads) == 1


@pytest.mark.parametrize(("question", "start"), [
    ("delete the oil filters", "I can't do that."),
    ("Supprime toutes les alertes", "Je ne peux pas faire ça."),
    ("احذف كل التنبيهات", "لا أستطيع فعل ذلك."),
    ("bdel stock dyal amortisseur l 10", "لا أستطيع فعل ذلك."),
])
def test_a_refusal_is_the_apps_own_sentence_in_the_persons_language(browser, shop, model, question, start):
    model(readings=[{**NOTHING, "type": "cannot_answer"}])
    result = done(chat(browser, question))
    assert result["question"]["type"] == "cannot_answer" and result["lookups"] == []
    assert result["text"].startswith(start) and result["written_by"] == "app"


# Follow-ups: read by the app as changes to the question before, never reusing old numbers

PADS_THIS_WEEK = {"type": "sales_of", "filters": {"part": "brake pads", "period": "this_week"}}


def test_and_in_rabat_changes_only_the_branch(browser, shop, model):
    fake = model()
    result = done(chat(browser, "and in Rabat?", PADS_THIS_WEEK))
    assert result["read_by"] == "follow_up" and fake.reads == []
    assert result["question"] == {"type": "sales_of", "filters": {"part": "brake pads", "branch": RABAT, "period": "this_week"}}
    assert result["lookups"][0]["values"]["pieces"] == 0


def test_why_about_a_part_explains_what_changed(browser, shop, model):
    model()
    question = done(chat(browser, "pourquoi ?", PADS_THIS_WEEK))["question"]
    assert question == {"type": "explain_part_change", "filters": {"part": "brake pads", "period": "this_week"}}


def test_a_follow_up_the_rule_cant_read_goes_to_the_model_as_same(browser, shop, model):
    fake = model(readings=[{**NOTHING, "type": "same", "branch": RABAT, "period": "last_week"}])
    result = done(chat(browser, "hmm kifach kanet f rbat simana li fatet", PADS_THIS_WEEK))
    assert result["read_by"] == "model"
    assert result["question"] == {"type": "sales_of", "filters": {"part": "brake pads", "branch": RABAT, "period": "last_week"}}
    assert "same" in fake.reads[0]["schema"]["properties"]["type"]["enum"]
    assert '"part": "brake pads"' in fake.reads[0]["instructions"], "the model sees the question before"


def test_a_previous_question_is_checked_like_any_other(browser, shop, model):
    model()
    chat(browser, "and in Rabat?", {"type": "sales_of", "filters": {"branch": "Tangier"}}, status=422)
    chat(browser, "and in Rabat?", {"type": "drop_tables", "filters": {}}, status=422)


# AI off, failures, permissions, shops

def test_ai_off_sends_one_line_so_the_website_uses_the_keyword_rule(browser, shop, monkeypatch):
    monkeypatch.setattr(llm, "is_on", lambda model=None: False)
    assert chat(browser, "what's going on?") == [{"type": "ai_off"}]
    assert browser.get("/api/ask/ai").json() == {"ai_on": False, "online": False}


def test_logged_out_people_cannot_chat(browser):
    assert browser.post("/api/ask/chat", json={"question": "hi"}).status_code == 401
    assert browser.get("/api/ask/ai").status_code == 401


def test_staff_get_no_money_in_what_is_shown(browser, shop, model):
    staff = staff_browser(browser)
    model()
    result = done(chat(staff, "how many oil filters did we sell this week?"))
    assert "money" not in result["lookups"][0]["values"]
    assert all(number["unit"] != "money" for number in result["lookups"][0]["numbers"])
    assert "MAD" not in result["text"]


def test_each_shop_only_sees_its_own_data(browser, shop, model):
    other = create_other_shop()
    other_oil = new_part(other.organization_id, "Oil filter", "Filters")
    sell(other.organization_id, other_oil, "Other Shop", days_ago=0, quantity=99)
    model()
    assert done(chat(browser, "how many oil filters did we sell this week?"))["lookups"][0]["values"]["pieces"] == 5
    other_owner = logged_in_browser("owner@other.ma", OWNER_PASSWORD)
    assert done(chat(other_owner, "how many oil filters did we sell this week?"))["lookups"][0]["values"]["pieces"] == 99


def test_asking_changes_nothing(browser, shop, model):
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(AuditLog))
    model()
    chat(browser, "what's going on?")
    chat(browser, "and the oil filters?", PADS_THIS_WEEK)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog)) == before


# The new lookups (today's shop: the oil filters and brake pads of tests/test_ask.py, "today" = LAST_DAY)

def lookup(shop_id, question_type: str, currency: str | None = "MAD", **filters):
    with SessionLocal() as db:
        return look_up(db, shop_id, currency, Question(question_type, **filters)).answer


def test_today_briefing(shop):
    add_alert(shop, "negative_stock", money_at_stake=5000)
    briefing = lookup(shop, "today_briefing").values
    week = briefing["sales_this_week"]
    assert week["pieces"] == 11  # oil 3 + 2, pads 6
    assert week["normal_week"] == 3  # pads 12 in one of the 4 weeks before
    assert week["percent_vs_normal"] == 267
    assert briefing["needs_action"]["count"] + briefing["worth_a_look"]["count"] == 1
    assert briefing["late_deliveries"]["count"] == 0 and briefing["to_order"]["lines"] == 0


def test_compare_branches(shop):
    values = lookup(shop, "compare_branches").values  # the last 30 days, against the 30 before
    assert [(row["branch"], row["pieces"], row["pieces_before"]) for row in values["branches"]] == [(MAIN, 21, 50), (RABAT, 2, 0)]
    assert values["branches"][0]["percent_change"] == -58 and values["branches"][1]["percent_change"] is None
    assert values["total_pieces"] == 23
    assert [row["pieces"] for row in lookup(shop, "compare_branches", category="Brakes").values["branches"]] == [18, 0]


def test_explain_part_change(shop):
    oil = select_part(shop, "Oil filter")
    shelve(shop, oil, MAIN, 7, expected_30d=20)
    with SessionLocal() as db:
        first = LAST_DAY - timedelta(days=20)
        db.add(StockOut(organization_id=shop, part_id=oil, branch_id=branch_named(shop, MAIN), first_day=first,
                        last_day=first + timedelta(days=4)))
        db.commit()
    values = lookup(shop, "explain_part_change", part="oil filter").values
    assert (values["pieces_now"], values["pieces_before"], values["percent_change"]) == (5, 50, -90)
    assert values["days_out_of_stock_now"] == 5 and values["days_out_of_stock_before"] == 0
    assert values["stock_now"] == 7 and values["expected_next_30_days"] == 20
    assert len(values["weekly_pieces"]) == 8 and values["weekly_pieces"][-1]["pieces"] == 5


def test_part_details(shop):
    oil = select_part(shop, "Oil filter")
    shelve(shop, oil, MAIN, 7, expected_30d=20)
    shelve(shop, oil, RABAT, 4)
    answer = lookup(shop, "part_details", part="oil filter")
    part = answer.values["parts"][0]
    assert part["stock_total"] == 11 and part["stock_by_branch"] == [{"branch": MAIN, "pieces": 7}, {"branch": RABAT, "pieces": 4}]
    assert part["sold_last_30_days"] == 5 and part["expected_next_30_days"] == 20
    assert "sale_price_money" in part
    assert "sale_price_money" not in lookup(shop, "part_details", currency=None, part="oil filter").values["parts"][0]


def test_lookups_that_need_a_part_ask_which_one(shop):
    assert lookup(shop, "part_details").key == "which_part_stock"
    assert lookup(shop, "explain_part_change", part="unicorn horn").key == "part_not_found"


# Finding numbers in text

@pytest.mark.parametrize(("written", "found"), [
    ("1234", ["1234"]), ("1,234", ["1,234"]), ("1 234", ["1 234"]), ("1.234,5", ["1.234,5"]), ("١٢٣٤", ["1234"]),
    ("12%", ["12"]), ("twenty-five", ["25"]),
])
def test_numbers_in_their_usual_forms_are_found(written, found):
    assert numbers_written(written) == found


def test_list_markers_are_not_numbers():
    assert numbers_written("Top parts:\n1. Oil filter\n2. Brake pads") == []


def test_number_words_in_four_languages():
    assert numbers_in_words("twenty-five parts") == ["25"]
    assert numbers_in_words("quatre-vingt pièces") == ["80"]
    assert numbers_in_words("خمسة وعشرون قطعة") == ["25"]
    assert numbers_in_words("jouj dyal les pièces") == ["2"]
    assert numbers_in_words("rien de neuf, this one") == []


def test_darija_letters_written_as_digits_are_not_numbers():
    assert numbers_written("3tini kolchi 3la radiateur, ch7al bi3na m3a 9aren") == []
    assert numbers_written("5W30 oil, 120MAD, 3 lines, H7") == ["5", "30", "120", "3", "7"]


# The keyword rule: new types, follow-ups, apostrophes, orders

def test_whats_is_not_read_as_a_part_called_s():
    assert read_with_rule("What's running out?", SHOP).type == "running_out"


@pytest.mark.parametrize(("text", "expected"), [
    ("What's going on today?", Question("today_briefing", period="today")),
    ("quoi de neuf", Question("today_briefing")),
    ("كيداير اليوم", Question("today_briefing", period="today")),
    ("compare Casablanca and Rabat this month", Question("compare_branches", period="this_month", branches=f"{CASA} | {RABAT}")),
    ("which branch sells the most oils", Question("compare_branches", category="Oils")),
    ("why are oil filters", Question("explain_part_change", part="oil filters")),
    ("tout sur les plaquettes", Question("part_details", part="plaquettes")),
])
def test_the_rule_reads_the_new_question_types(text, expected):
    assert read_with_rule(text, SHOP) == expected


@pytest.mark.parametrize("text", ["Passe une commande de 20 radiateurs chez Valeo", "place an order for 20 radiators"])
def test_asking_the_app_to_place_an_order_is_refused(text):
    assert read_with_rule(text, SHOP).type == "cannot_answer"


EARLIER = Question("sales_of", part="brake pads", branch=CASA, period="this_week")


@pytest.mark.parametrize(("text", "expected"), [
    ("and in Rabat?", Question("sales_of", part="brake pads", branch=RABAT, period="this_week")),
    ("w f rbat?", Question("sales_of", part="brake pads", branch=RABAT, period="this_week")),
    ("وفي الرباط؟", Question("sales_of", part="brake pads", branch=RABAT, period="this_week")),
    ("et le mois dernier ?", Question("sales_of", part="brake pads", branch=CASA, period="last_month")),
    ("and the oil filters?", Question("sales_of", part="oil filters", branch=CASA, period="this_week")),
    ("why?", Question("explain_part_change", part="brake pads", branch=CASA, period="this_week")),
    ("3lach?", Question("explain_part_change", part="brake pads", branch=CASA, period="this_week")),
])
def test_follow_ups_change_the_question_before(text, expected):
    assert read_follow_up(text, EARLIER, SHOP) == expected


@pytest.mark.parametrize("text", ["what should I order?", "compare Casablanca and Rabat", "hello there friend", "zzz"])
def test_a_question_of_its_own_is_not_a_follow_up(text):
    assert read_follow_up(text, EARLIER, SHOP) is None


def test_why_after_a_question_without_a_part_asks_it_again():
    assert read_follow_up("why?", Question("running_out"), SHOP) == Question("running_out")


def test_the_model_reader_merges_a_same_reading_into_the_question_before(monkeypatch):
    monkeypatch.setattr(llm, "ask_json", lambda *args, **kwargs: {**NOTHING, "type": "same", "branch": RABAT})
    assert model_reader.read_with_model("kifach f rbat", SHOP, earlier=EARLIER) == Question(
        "sales_of", part="brake pads", branch=RABAT, period="this_week")
    instructions = model_reader.instructions_for(SHOP)
    assert "3lach na9so" in instructions and "عطيني كلشي" in instructions, "Darija examples, in both scripts"


def test_comparing_two_branches_answers_about_those_two(shop):
    with SessionLocal() as db:
        db.add(Branch(organization_id=shop, name="Marrakech - Gueliz"))
        db.commit()
    values = lookup(shop, "compare_branches", branches=f"{RABAT} | {MAIN}").values
    assert [row["branch"] for row in values["branches"]] == [MAIN, RABAT] and values["only_asked"] is True
    assert len(lookup(shop, "compare_branches").values["branches"]) == 3, "without names: every branch"


def test_the_model_can_name_the_branches_to_compare(monkeypatch):
    monkeypatch.setattr(llm, "ask_json", lambda *args, **kwargs: {
        **NOTHING, "type": "compare_branches", "branches": [CASA, RABAT], "period": "this_month"})
    assert model_reader.read_with_model("9aren bin casa w rbat had chhar", SHOP) == Question(
        "compare_branches", period="this_month", branches=f"{CASA} | {RABAT}")
    assert model_reader.schema_for(SHOP)["properties"]["branches"]["items"]["enum"] == [CASA, RABAT]


@pytest.mark.parametrize("branches", [f"{CASA} | Tangier", CASA, ""])
def test_branches_to_compare_must_be_two_of_the_shops_own(branches):
    assert checked_question({"type": "compare_branches", "branches": branches}, SHOP) in (None, Question("compare_branches"))
