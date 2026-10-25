"""The "Ask your shop" assistant: the app reads the question (rule, follow-up, or the model as strict
JSON), runs one read-only lookup, and the model writes the answer with fact labels ([F1]) that the app
replaces with the real numbers. Each sentence is checked before it is shown: no number typed by the
model, and every label next to its own branch, part, period and direction. Also: money hidden from
staff, each shop sees only its own data.

The model is a scripted fake here: these tests check the app around it, not the model itself
(that is measured by app/ask/check_assistant.py on the 60 open questions).
"""

import copy
import json
import re
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.ai import llm
from app.ask import model_reader
from app.ask.answer_language import written_in
from app.ask.assistant import DARIJA_ANSWER, MONEY_HIDDEN
from app.ask.fact_check import FactText
from app.ask.keyword_rule import read_follow_up, read_with_rule
from app.ask.labeled_facts import Fact, labeled_facts
from app.ask.number_check import numbers_in_words, numbers_written
from app.ask.question import Question, ShopWords
from app.ask.tools import look_up
from app.db import SessionLocal
from app.models import AuditLog, StockOut
from tests.helpers import OWNER_PASSWORD, create_other_shop, logged_in_browser
from tests.test_ask import (  # noqa: F401  (shop and several_brake_pads_shop are fixtures)
    LAST_DAY, MAIN, RABAT, branch_named, new_part, select_part, sell, shelve, several_brake_pads_shop, shop,
    staff_browser,
)
from tests.test_today import add_alert

CASA = "Casablanca - Maarif"
SHOP = ShopWords(categories=("Brakes", "Oils"), branches=(CASA, RABAT), part_words=frozenset(
    {"brake", "pads", "oil", "filter", "filters", "plaquettes"}))
NOTHING = {"part": None, "category": None, "branch": None, "period": None}


class FakeModel:
    """Plays back scripted writing and readings, and remembers what it was sent. A scripted writing is
    a list of pieces, or a function of the writer's prompt (to find a fact's label in it). When the
    script runs out, the last writing is given again (a writer that makes the same mistake twice)."""

    def __init__(self, writes: list, readings: list[object]):
        self.writes, self.readings = list(writes), list(readings)
        self.chats: list[list[dict]] = []
        self.reads: list[dict] = []
        self.pieces_sent = 0

    def chat(self, messages, model=None, longest=None):
        assert longest, "the writer is always limited in length"
        self.chats.append(copy.deepcopy(messages))
        reply = self.writes.pop(0) if len(self.writes) > 1 else self.writes[0]  # the last one again, for a retry
        for piece in reply(messages[0]["content"]) if callable(reply) else reply:
            self.pieces_sent += 1
            yield {"text": piece}

    def ask_json(self, instructions, text, schema, model=None):
        self.reads.append({"instructions": instructions, "text": text, "schema": schema})
        return self.readings.pop(0)


@pytest.fixture
def model(monkeypatch):
    """model(writes=[...], readings=[json, ...]) installs a fake model and returns it."""
    monkeypatch.setattr(llm, "is_on", lambda model=None: True)

    def install(writes=(), readings=()):
        fake = FakeModel(list(writes), list(readings))
        monkeypatch.setattr(llm, "chat", fake.chat)
        monkeypatch.setattr(llm, "ask_json", fake.ask_json)
        return fake

    return install


def label(prompt: str, *words: str) -> str:
    """The label of the first fact line in the writer's prompt that has all these words."""
    for line in prompt.splitlines():
        found = re.match(r"\[(F\d+)\] (.*)", line)
        if found and all(word in found.group(2) for word in words):
            return f"[{found.group(1)}]"
    raise AssertionError(f"no fact with {words} in:\n{prompt}")


def chat(browser, question: str, previous: dict | None = None, status: int = 200) -> list[dict]:
    response = browser.post("/api/ask/chat", json={"question": question, "previous": previous})
    assert response.status_code == status, response.text
    if status != 200:
        return []
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in response.text.splitlines() if line]


def chat_with(model, write, browser, question: str) -> list[dict]:
    model(writes=[write])
    return chat(browser, question)


def done(events: list[dict]) -> dict:
    assert events[-1]["type"] == "done"
    return events[-1]


def shown(events: list[dict]) -> str:
    return "".join(event["text"] for event in events if event["type"] == "text")


def writer_prompt(fake: FakeModel, call: int = 0) -> str:
    return fake.chats[call][0]["content"]


# Read, look up, write with labels

def test_the_writer_uses_labels_and_the_app_puts_the_numbers_in(browser, shop, model):
    def write(prompt):
        return [f"We sold {label(prompt, 'pieces sold')} oil ", "filters this week. ", f"That is {label(prompt, 'sales value')}."]

    fake = model(writes=[write])
    events = chat(browser, "how many oil filters did we sell this week?")
    assert events[0] == {"type": "looking_up", "tool": "sales_of", "filters": {"part": "oil filters", "period": "this_week"}}
    result = done(events)
    assert result["read_by"] == "rule" and fake.reads == [], "the model isn't asked to read what the rule is sure of"
    assert result["question"] == {"type": "sales_of", "filters": {"part": "oil filters", "period": "this_week"}}
    assert result["checked"] is True and result["text"] == "We sold 5 oil filters this week. That is MAD 500.00."
    # Sent sentence by sentence, with the numbers already in.
    assert [event["text"] for event in events if event["type"] == "text"] == ["We sold 5 oil filters this week.", " That is MAD 500.00."]
    # The writer never sees the numbers themselves, only what each label is.
    facts = [line for line in writer_prompt(fake).splitlines() if line.startswith("[F")]
    assert facts and not any(re.search(r"\d", line.split("] ", 1)[1]) for line in facts)
    assert result["lookups"][0]["sentence"].startswith("Oil filter: 5 pieces sold")


def test_numbers_are_written_the_way_the_answers_language_writes_them(browser, shop, model):
    model(writes=[lambda prompt: [f"Valeur : {label(prompt, 'sales value')}."]])
    assert done(chat(browser, "combien de filtres a huile vendus cette semaine ?"))["text"] == "Valeur : 500,00 DH."


def test_a_number_typed_by_the_model_blocks_the_answer(browser, shop, model):
    fake = model(writes=[lambda prompt: [f"We sold {label(prompt, 'pieces sold')} oil filters this week. ", "Next week 77. ", "Great!"]])
    events = chat(browser, "how many oil filters did we sell this week?")
    result = done(events)
    assert result["checked"] is False and result["wrong_numbers"] == ["typed number 77"]
    assert "77" not in shown(events) and "Great" not in shown(events)
    assert result["lookups"], "the website shows the app's own sentences from these instead"
    assert len(fake.chats) == 2 and result["retried"] is True, "one second try, then the app's own answer"
    assert "you typed the number 77 yourself; use labels only" in fake.chats[1][-1]["content"]


@pytest.mark.parametrize("typed", ["We sold 5 oil filters.", "We sold ٥ oil filters.", "We sold ninety-seven oil filters."])
def test_digits_arabic_digits_and_number_words_typed_by_the_model_are_all_blocked(browser, shop, model, typed):
    model(writes=[[typed]])
    assert done(chat(browser, "how many oil filters did we sell this week?"))["checked"] is False


def test_the_right_number_on_the_wrong_branch_is_blocked(browser, shop, model):
    # The last 30 days: the main branch sold 21 pieces, Rabat 2. The writer gives the main branch's number to Rabat.
    def swapped(prompt):
        return [f"Rabat sold {label(prompt, MAIN, 'this period', 'pieces sold')} pieces."]

    result = done(chat_with(model, swapped, browser, "compare Atlas and Rabat"))
    assert result["checked"] is False and "written next to Rabat - Agdal" in result["wrong_numbers"][0]

    def right(prompt):
        return [f"Rabat sold {label(prompt, RABAT, 'this period', 'pieces sold')} pieces, "
                f"Atlas {label(prompt, MAIN, 'this period', 'pieces sold')}."]

    assert done(chat_with(model, right, browser, "compare Atlas and Rabat"))["text"] == "Rabat sold 2 pieces, Atlas 21."


def test_the_right_number_on_the_wrong_period_is_blocked(browser, shop, model):
    # Brake pads: 6 this week, 12 the week before.
    def wrong(prompt):
        return [f"Brake pads sold {label(prompt, 'the period before', 'pieces sold')} pieces this week."]

    assert done(chat_with(model, wrong, browser, "brake pads sales compared to last week"))["checked"] is False

    def right(prompt):
        return [f"Brake pads sold {label(prompt, 'this period', 'pieces sold')} this week, against "
                f"{label(prompt, 'the period before', 'pieces sold')} the week before, {label(prompt, 'change')} down."]

    result = done(chat_with(model, right, browser, "brake pads sales compared to last week"))
    assert result["text"] == "Brake pads sold 6 this week, against 12 the week before, -50% down."


def test_a_change_in_the_wrong_direction_is_blocked(browser, shop, model):
    def wrong(prompt):
        return [f"Brake pad sales went up {label(prompt, 'change')}."]

    assert done(chat_with(model, wrong, browser, "brake pads sales compared to last week"))["checked"] is False


def test_the_right_number_on_the_wrong_part_is_blocked(browser, several_brake_pads_shop, model):
    # In stock: front 30, rear 20, premium 10. The writer gives the front pads' stock to the rear ones.
    def wrong(prompt):
        return [f"The rear pads have {label(prompt, 'Brake pads front', 'pieces in stock')} in stock."]

    assert done(chat_with(model, wrong, browser, "details of the brake pads"))["checked"] is False

    def right(prompt):
        return [f"The rear pads have {label(prompt, 'Brake pads rear', 'pieces in stock')} in stock, "
                f"the front ones {label(prompt, 'Brake pads front', 'pieces in stock')}."]

    assert done(chat_with(model, right, browser, "details of the brake pads"))["text"] == "The rear pads have 20 in stock, the front ones 30."


def test_a_blocked_answer_is_written_again_once_told_exactly_what_was_wrong(browser, shop, model):
    def swapped(prompt):
        return [f"Rabat sold {label(prompt, MAIN, 'this period', 'pieces sold')} pieces."]

    def right(prompt):
        return [f"Rabat sold {label(prompt, RABAT, 'this period', 'pieces sold')} pieces."]

    fake = model(writes=[swapped, right])
    result = done(chat(browser, "compare Atlas and Rabat"))
    assert result["checked"] is True and result["retried"] is True and result["text"] == "Rabat sold 2 pieces."
    second_try = fake.chats[1]
    assert second_try[-2] == {"role": "assistant", "content": swapped(writer_prompt(fake))[0]}
    assert "is the number for Atlas Parts, but you put it next to Rabat - Agdal" in second_try[-1]["content"]


def test_text_already_shown_is_taken_back_before_the_second_try(browser, shop, model):
    def first(prompt):
        return [f"We sold {label(prompt, 'pieces sold')} oil filters. ", "And 77 more."]

    def second(prompt):
        return [f"We sold {label(prompt, 'pieces sold')} oil filters this week."]

    model(writes=[first, second])
    events = chat(browser, "how many oil filters did we sell this week?")
    kinds = [event["type"] for event in events]
    assert kinds == ["looking_up", "text", "restart", "text", "done"]
    assert done(events)["text"] == "We sold 5 oil filters this week."


def test_an_answer_that_is_right_the_first_time_is_not_written_twice(browser, shop, model):
    fake = model(writes=[lambda prompt: [f"We sold {label(prompt, 'pieces sold')} oil filters."]])
    assert done(chat(browser, "how many oil filters did we sell this week?"))["retried"] is False
    assert len(fake.chats) == 1


def test_an_answer_in_the_wrong_language_is_written_again_in_the_right_one(browser, shop, model):
    def english(prompt):
        return [f"We sold {label(prompt, 'pieces sold')} oil filters this week."]

    def french(prompt):
        return [f"Cette semaine, {label(prompt, 'pieces sold')} filtres à huile ont été vendus."]

    fake = model(writes=[english, french])
    events = chat(browser, "combien de filtres a huile vendus cette semaine ?")
    result = done(events)
    assert result["checked"] is True and result["retried"] is True
    assert result["text"] == "Cette semaine, 5 filtres à huile ont été vendus."
    assert "you answered in the wrong language; answer in French" in fake.chats[1][-1]["content"]
    assert [event["type"] for event in events] == ["looking_up", "text", "restart", "text", "done"]


def test_an_answer_in_the_wrong_language_twice_shows_the_apps_own_answer(browser, shop, model):
    fake = model(writes=[lambda prompt: [f"We sold {label(prompt, 'pieces sold')} oil filters this week."]])
    result = done(chat(browser, "ما هي مبيعات فلاتر الزيت هذا الأسبوع؟"))
    assert result["checked"] is False and result["text"] == "" and result["lookups"]
    assert result["wrong_numbers"] == ["wrong language, the question is in Arabic"]
    assert len(fake.chats) == 2


@pytest.mark.parametrize(("text", "found"), [
    ("Rabat - Agdal sold 6 980 pieces last month.", "en"),
    ("Cette semaine, 5 362 pièces ont été vendues.", "fr"),
    ("الدار البيضاء - Maarif باع 6 349 هذا الشهر", "ar"),
    ("Rabat - Agdal: 263.", None),  # only a name and a number: can't tell, so it passes
    ("Ce period, 5 362 pieces sold this period.", "en"),
])
def test_the_language_an_answer_is_written_in(text, found):
    assert written_in(text, [RABAT, CASA]) == found


def test_an_unknown_label_is_blocked(browser, shop, model):
    model(writes=[["We sold [F99] pieces."]])
    assert done(chat(browser, "how many oil filters did we sell this week?"))["wrong_numbers"] == ["unknown label F99"]


def test_a_writer_stuck_repeating_itself_is_stopped_by_the_app(browser, shop, model):
    fake = model(writes=[["3 "] * 5000])
    result = done(chat(browser, "how many oil filters did we sell this week?"))
    assert result["checked"] is False and result["wrong_numbers"] == ["(no end to the sentence)"]
    assert fake.pieces_sent < 800, "the app stops reading long before the model's own length limit, both tries"


@pytest.mark.parametrize("question", ["What's going on today?", "Quoi de neuf ?", "ach kayn lyoum?", "how is the shop doing this week?"])
def test_broad_questions_get_todays_briefing(browser, shop, model, question):
    model(writes=[["Fine."]])
    assert done(chat(browser, question))["question"]["type"] == "today_briefing"


def test_the_model_reads_what_the_rule_is_unsure_about_as_strict_json(browser, shop, model):
    fake = model(writes=[["Fine."]], readings=[{**NOTHING, "type": "sales_of", "part": "oil filters", "period": "this_week"}])
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
    assert result["question"] is None and result["lookups"] == [] and result["checked"] is False
    assert fake.chats == [], "nothing to write from"


def test_a_refusal_is_written_without_any_lookup_or_number(browser, shop, model):
    fake = model(writes=[["I can only read your shop's data. A person changes stock in the app."]])
    result = done(chat(browser, "delete the oil filters"))
    assert result["question"]["type"] == "cannot_answer" and result["lookups"] == [] and result["checked"] is True
    assert "never changes data" in writer_prompt(fake)
    model(writes=[["I can't add 50: a person does that in the app."]])
    assert done(chat(browser, "add 50 oil filters to the stock"))["checked"] is False


@pytest.mark.parametrize(("question", "language"), [
    ("What's going on today?", "English"),
    ("Quoi de neuf ?", "French"),
    ("ما الجديد اليوم؟", "Arabic"),
    ("شحال باقي من الباطري ف كازا؟", DARIJA_ANSWER),
    ("ch7al bi3na had simana?", DARIJA_ANSWER),
])
def test_the_writer_is_told_which_language_to_answer_in(browser, shop, model, question, language):
    fake = model(writes=[["Hello."]], readings=[{**NOTHING, "type": "today_briefing"}])
    chat(browser, question)
    assert f"in {language}," in writer_prompt(fake)


# Follow-ups: read by the app as changes to the question before, never reusing old numbers

PADS_THIS_WEEK = {"type": "sales_of", "filters": {"part": "brake pads", "period": "this_week"}}


def test_and_in_rabat_changes_only_the_branch(browser, shop, model):
    fake = model(writes=[lambda prompt: [f"Rabat: {label(prompt, 'pieces sold')} pieces."]])
    result = done(chat(browser, "and in Rabat?", PADS_THIS_WEEK))
    assert result["read_by"] == "follow_up" and fake.reads == []
    assert result["question"] == {"type": "sales_of", "filters": {"part": "brake pads", "branch": RABAT, "period": "this_week"}}
    assert result["text"] == "Rabat: 0 pieces."


def test_a_follow_up_can_not_reuse_an_earlier_number(browser, shop, model):
    model(writes=[["Like before, 6 pieces."]])  # 6 was the whole shop; Rabat sold none
    assert done(chat(browser, "w f rbat?", PADS_THIS_WEEK))["checked"] is False


def test_why_about_a_part_explains_what_changed(browser, shop, model):
    model(writes=[["Down."]])
    question = done(chat(browser, "pourquoi ?", PADS_THIS_WEEK))["question"]
    assert question == {"type": "explain_part_change", "filters": {"part": "brake pads", "period": "this_week"}}


def test_a_follow_up_the_rule_cant_read_goes_to_the_model_as_same(browser, shop, model):
    fake = model(writes=[["Fine."]], readings=[{**NOTHING, "type": "same", "branch": RABAT, "period": "last_week"}])
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
    assert browser.get("/api/ask/ai").json() == {"ai_on": False}


def test_a_model_failing_before_anything_was_shown_counts_as_ai_off(browser, shop, monkeypatch):
    monkeypatch.setattr(llm, "is_on", lambda model=None: True)

    def broken(*args, **kwargs):
        raise llm.ModelFailed("timed out")
        yield  # a generator, like the real one

    monkeypatch.setattr(llm, "chat", broken)
    assert chat(browser, "delete everything") == [{"type": "ai_off"}]


def test_logged_out_people_cannot_chat(browser):
    assert browser.post("/api/ask/chat", json={"question": "hi"}).status_code == 401
    assert browser.get("/api/ask/ai").status_code == 401


MONEY_WORDS = ("sales value", "cost", "price")


def test_staff_get_no_money_in_what_the_model_reads_or_what_is_shown(browser, shop, model):
    staff = staff_browser(browser)
    fake = model(writes=[["Fine."]])
    result = done(chat(staff, "how many oil filters did we sell this week?"))
    assert "money" not in result["lookups"][0]["values"]
    assert all(number["unit"] != "money" for number in result["lookups"][0]["numbers"])
    assert MONEY_HIDDEN in writer_prompt(fake) and "MAD" not in writer_prompt(fake)
    with SessionLocal() as db:
        for question_type in ("today_briefing", "compare_branches", "explain_part_change", "part_details", "sales_of",
                              "what_to_order", "dead_stock", "sales_vs_last"):
            part = "oil filter" if question_type in ("explain_part_change", "part_details") else None
            question = Question(question_type, part=part)
            facts = labeled_facts(look_up(db, shop, None, question).answer, question, None, "en")
            assert not any(word in fact.what for fact in facts for word in MONEY_WORDS), question_type


def test_each_shop_only_sees_its_own_data(browser, shop, model):
    other = create_other_shop()
    other_oil = new_part(other.organization_id, "Oil filter", "Filters")
    sell(other.organization_id, other_oil, "Other Shop", days_ago=0, quantity=99)
    model(writes=[lambda prompt: [f"{label(prompt, 'pieces sold')}."]])
    assert done(chat(browser, "how many oil filters did we sell this week?"))["text"] == "5."
    model(writes=[lambda prompt: [f"{label(prompt, 'pieces sold')}."]])
    other_owner = logged_in_browser("owner@other.ma", OWNER_PASSWORD)
    assert done(chat(other_owner, "how many oil filters did we sell this week?"))["text"] == "99."


def test_asking_changes_nothing(browser, shop, model):
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(AuditLog))
    model(writes=[["Fine."], ["Fine."]])
    chat(browser, "what's going on?")
    chat(browser, "and the oil filters?", PADS_THIS_WEEK)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog)) == before


# The check itself, on hand-made facts

FACTS = [
    Fact("F1", "pieces sold", 4288, "4,288", branch=RABAT, when="now"),
    Fact("F2", "pieces sold", 6349, "6,349", branch=CASA, when="now"),
    Fact("F3", "pieces sold", 4574, "4,574", branch=RABAT, when="before"),
    Fact("F4", "change in pieces sold", "-6%", "-6%", branch=RABAT, direction="down"),
    Fact("F5", "pieces in stock", 30, "30", part="Alternator - Kia Picanto 1.0"),
    Fact("F6", "pieces in stock", 12, "12", part="Alternator - Renault Clio 4 1.5 dCi"),
    Fact("F7", "parts running out within 14 days", 25, "25"),
]


def problems(text: str) -> list[str]:
    return FactText(FACTS, (CASA, RABAT)).problems(text)


@pytest.mark.parametrize("text", [
    "Rabat sold [F1] pieces this month, Casablanca [F2].",
    "[F1] pieces in Rabat and [F2] in Casablanca.",
    "الدار البيضاء ب [F2] قطعة، والرباط ب [F1] قطعة.",
    "Rabat sold [F1] this month against [F3] the month before, [F4] down.",
    "The Picanto 1.0 has [F5] in stock, the Clio 4 1.5 dCi [F6].",
    "[F7] parts run out within 14 days.",
    "3tini kolchi: [F7] parts.",
])
def test_labels_next_to_their_own_branch_part_period_and_direction_pass(text):
    assert problems(text) == []


@pytest.mark.parametrize(("text", "problem"), [
    ("Casablanca sold [F1] pieces.", "[F1] is Rabat - Agdal, written next to Casablanca - Maarif"),
    ("الدار البيضاء ب [F1] قطعة، والرباط ب [F1] قطعة.", "[F1] is Rabat - Agdal, written next to Casablanca - Maarif"),
    ("Rabat sold [F3] pieces this month.", "[F3] is before, written next to now"),
    ("The Clio has [F5] in stock.", "[F5] is Alternator - Kia Picanto 1.0, written next to Alternator - Renault Clio 4 1.5 dCi"),
    ("Rabat is up [F4].", "[F4] is down, written next to up"),
    ("Rabat sold 4288 pieces.", "typed number 4288"),
    ("Rabat sold ٤٢٨٨ pieces.", "typed number 4288"),
    ("Rabat sold four thousand pieces.", "typed number 4000"),
    ("Rabat sold [F9].", "unknown label F9"),
])
def test_a_label_next_to_someone_else_or_a_typed_number_is_a_problem(text, problem):
    assert problems(text)[0] == problem


def test_when_the_question_is_about_last_month_last_month_is_this_period():
    asked_last_month = FactText(FACTS, (CASA, RABAT), period="last_month")
    assert asked_last_month.problems("Rabat sold [F1] pieces last month, against [F3] the month before.") == []
    assert asked_last_month.problems("Rabat sold [F3] pieces last month.") != []


def test_the_text_is_let_out_sentence_by_sentence_with_numbers_in_and_stops_at_the_first_problem():
    text = FactText(FACTS, (CASA, RABAT))
    assert text.add("Rabat sold [F1]") == ""
    assert text.add(" pieces. Casablanca [F1]") == "Rabat sold 4,288 pieces."
    assert text.add(" too. Fine.") == ""
    assert text.wrong == ["[F1] is Rabat - Agdal, written next to Casablanca - Maarif"]
    assert text.finish() == ""
    assert text.shown == "Rabat sold 4,288 pieces."


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
    ("What's going on today?", Question("today_briefing")),
    ("quoi de neuf", Question("today_briefing")),
    ("كيداير اليوم", Question("today_briefing")),
    ("compare Casablanca and Rabat this month", Question("compare_branches", period="this_month")),
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
