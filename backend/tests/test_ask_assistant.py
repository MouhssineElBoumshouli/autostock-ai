"""The "Ask your shop" assistant: read-only lookups the model may call, every written number checked
against them before it is shown, follow-ups, money hidden from staff, each shop sees only its own data.

The model is a scripted fake here: these tests check the app around it, not the model itself
(that is measured by app/ask/check_assistant.py on the 60 open questions).
"""

import copy
import json
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.ai import llm
from app.ask.assistant import MONEY_HIDDEN, CheckedText
from app.ask.keyword_rule import read_with_rule
from app.ask.number_check import AllowedNumbers, numbers_in_words, numbers_written
from app.ask.question import ShopWords
from app.ask.tools import TOOLS, for_the_model, look_up
from app.ask.understand import shop_words
from app.db import SessionLocal
from app.models import AuditLog, StockOut
from tests.helpers import OWNER_PASSWORD, create_other_shop, logged_in_browser
from tests.test_ask import (  # noqa: F401  (shop is a fixture)
    LAST_DAY, MAIN, RABAT, branch_named, new_part, select_part, sell, shelve, shop, staff_browser,
)
from tests.test_today import add_alert


class FakeModel:
    """Plays back one scripted reply per call and remembers what it was sent."""

    def __init__(self, *replies: list[dict]):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def __call__(self, messages, tools=None, model=None):
        self.calls.append({"messages": copy.deepcopy(messages), "tools": tools})
        yield from self.replies.pop(0)


def looks_up(*calls: tuple[str, dict]) -> list[dict]:
    return [{"tool_calls": [{"function": {"name": name, "arguments": arguments}} for name, arguments in calls]}]


def writes(*pieces: str) -> list[dict]:
    return [{"text": piece} for piece in pieces]


@pytest.fixture
def model(monkeypatch):
    """Installs a fake model: model(reply, reply, ...) returns it."""
    monkeypatch.setattr(llm, "is_on", lambda model=None: True)

    def install(*replies):
        fake = FakeModel(*replies)
        monkeypatch.setattr(llm, "chat", fake)
        return fake

    return install


def chat(browser, question: str, earlier: list[dict] | None = None) -> list[dict]:
    response = browser.post("/api/ask/chat", json={"question": question, "earlier": earlier or []})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in response.text.splitlines() if line]


def done(events: list[dict]) -> dict:
    assert events[-1]["type"] == "done"
    return events[-1]


def shown(events: list[dict]) -> str:
    return "".join(event["text"] for event in events if event["type"] == "text")


# The conversation

def test_it_looks_up_then_writes_and_every_number_is_checked(browser, shop, model):
    model(looks_up(("sales_of", {"part": "oil filters", "period": "this_week"})),
          writes("We sold 5 oil ", "filters this week. ", "That is 500 MAD."))
    events = chat(browser, "how are oil filters doing this week?")
    assert events[0] == {"type": "looking_up", "tool": "sales_of", "filters": {"part": "oil filters", "period": "this_week"}}
    result = done(events)
    assert result["checked"] is True and result["wrong_numbers"] == []
    assert result["text"] == "We sold 5 oil filters this week. That is 500 MAD."
    # Sent sentence by sentence, never half a number.
    assert [event["text"] for event in events if event["type"] == "text"] == ["We sold 5 oil filters this week.", " That is 500 MAD."]
    # The numbers used, shown under the answer, with the app's own sentence for each lookup.
    assert result["lookups"][0]["tool"] == "sales_of" and result["lookups"][0]["values"]["pieces"] == 5
    assert result["lookups"][0]["sentence"].startswith("Oil filter: 5 pieces sold")


def test_a_wrong_number_stops_the_answer_before_it_is_shown(browser, shop, model):
    model(looks_up(("sales_of", {"part": "oil filters", "period": "this_week"})),
          writes("We sold 5 oil filters this week. ", "Next week we will sell 77. ", "Great!"))
    events = chat(browser, "oil filters this week?")
    result = done(events)
    assert result["checked"] is False and result["wrong_numbers"] == ["77"]
    assert "77" not in shown(events) and "Great" not in shown(events)
    assert result["lookups"], "the website shows the app's own sentences from these instead"


def test_simple_arithmetic_on_looked_up_numbers_is_allowed(browser, shop, model):
    # Brake pads: 6 this week, 12 the week before.
    model(looks_up(("sales_vs_last", {"part": "brake pads", "period": "this_week"})),
          writes("Brake pads: 6 this week against 12, so 6 fewer, down 50%. ", "Roughly half (0.5 times)."))
    assert done(chat(browser, "brake pads vs last week?"))["checked"] is True


def test_numbers_written_in_words_are_checked_too(browser, shop, model):
    model(looks_up(("sales_of", {"part": "oil filters", "period": "this_week"})), writes("We sold ninety-seven oil filters."),
          writes("Yes, ninety-seven."))
    assert done(chat(browser, "oil filters this week?"))["wrong_numbers"] == ["97"]


def test_a_number_without_any_lookup_fails_even_after_one_more_try(browser, shop, model):
    fake = model(writes("You sold 42 pieces today."), writes("Still 42."))
    result = done(chat(browser, "how was today?"))
    assert result["checked"] is False and result["lookups"] == []
    assert "these numbers are not in what you looked up: 42" in fake.calls[1]["messages"][-1]["content"]


def test_a_blocked_answer_gets_one_more_try_when_nothing_was_shown(browser, shop, model):
    model(writes("You sold 42 oil filters."),
          looks_up(("sales_of", {"part": "oil filters", "period": "this_week"})),
          writes("You sold 5 oil filters this week."))
    result = done(chat(browser, "oil filters this week?"))
    assert result["checked"] is True and result["text"] == "You sold 5 oil filters this week."


def test_no_second_try_once_part_of_the_answer_was_shown(browser, shop, model):
    fake = model(looks_up(("sales_of", {"part": "oil filters", "period": "this_week"})),
                 writes("You sold 5 oil filters. And 42 brake pads."))
    result = done(chat(browser, "oil filters this week?"))
    assert result["checked"] is False and len(fake.calls) == 2


@pytest.mark.parametrize(("question", "language"), [
    ("What's going on today?", "English"),
    ("Quoi de neuf ?", "French"),
    ("ما الجديد اليوم؟", "Arabic"),
    ("شحال باقي من الباطري ف كازا؟", "Moroccan Darija, in Arabic letters"),
    ("ch7al bi3na had simana?", "Moroccan Darija, in Latin letters (like the question)"),
])
def test_the_model_is_told_which_language_to_answer_in(browser, shop, model, question, language):
    fake = model(writes("Hello."))
    chat(browser, question)
    assert f"Reply in {language}." in fake.calls[0]["messages"][0]["content"]


def test_several_lookups_in_one_answer(browser, shop, model):
    model(looks_up(("sales_of", {"branch": MAIN, "period": "this_week"}), ("sales_of", {"branch": "rabat", "period": "this_week"})),
          writes("Main shop 9 pieces, Rabat 2 pieces."))
    result = done(chat(browser, "compare the main shop and Rabat this week"))
    assert [lookup["filters"]["branch"] for lookup in result["lookups"]] == [MAIN, RABAT]
    assert result["checked"] is True


def test_it_can_look_up_more_after_seeing_a_first_result(browser, shop, model):
    fake = model(looks_up(("today_briefing", {})), looks_up(("stock_of_part", {"part": "oil filter"})), writes("All good."))
    result = done(chat(browser, "what's going on?"))
    assert [lookup["tool"] for lookup in result["lookups"]] == ["today_briefing", "stock_of_part"]
    assert fake.calls[0]["tools"] and fake.calls[1]["tools"]
    assert fake.calls[2]["tools"] is None, "the last round must answer, not look up again"


def test_a_refusal_needs_no_lookup(browser, shop, model):
    model(writes("I can only read your shop's data. A person changes stock on the Stock page."))
    result = done(chat(browser, "set the stock of oil filters to 50"))
    assert result["checked"] is True and result["lookups"] == []


def test_the_persons_own_numbers_may_be_repeated(browser, shop, model):
    model(writes("I can't set the stock to 50: a person does that in the app."))
    assert done(chat(browser, "set the stock of oil filters to 50"))["checked"] is True


def test_a_problem_with_a_lookup_is_told_to_the_model(browser, shop, model):
    fake = model(looks_up(("sales_of", {"branch": "Tangier"}), ("delete_stock", {})), writes("There is no Tangier branch."))
    result = done(chat(browser, "sales in Tangier"))
    tool_messages = [message for message in fake.calls[1]["messages"] if message["role"] == "tool"]
    assert "no branch called 'Tangier'" in tool_messages[0]["content"]
    assert "no tool called 'delete_stock'" in tool_messages[1]["content"]
    assert result["lookups"] == []


# Follow-ups

def test_follow_ups_keep_the_conversation(browser, shop, model):
    fake = model(looks_up(("sales_of", {"part": "oil filters", "branch": "Rabat", "period": "this_week"})), writes("2 in Rabat."))
    earlier = [{"question": "oil filters sold this week?", "answer": "We sold 5 oil filters this week."}]
    result = done(chat(browser, "and in Rabat?", earlier))
    messages = fake.calls[0]["messages"]
    assert [message["role"] for message in messages] == ["system", "user", "assistant", "user"]
    assert messages[1]["content"] == "oil filters sold this week?" and messages[3]["content"] == "and in Rabat?"
    assert result["checked"] is True and result["lookups"][0]["values"]["pieces"] == 2


def test_numbers_from_earlier_answers_must_be_looked_up_again(browser, shop, model):
    model(writes("Like I said, 5."), writes("Still 5."))
    earlier = [{"question": "oil filters this week?", "answer": "We sold 5 oil filters this week."}]
    assert done(chat(browser, "how many again?", earlier))["checked"] is False


def test_only_the_last_three_turns_are_kept(browser, shop, model):
    model(writes("Hello."))
    turn = {"question": "hi", "answer": "Hello."}
    response = browser.post("/api/ask/chat", json={"question": "hi", "earlier": [turn] * 4})
    assert response.status_code == 422


# AI off, failures, permissions, shops

def test_ai_off_sends_one_line_so_the_website_uses_the_keyword_rule(browser, shop, monkeypatch):
    monkeypatch.setattr(llm, "is_on", lambda model=None: False)
    assert chat(browser, "what's going on?") == [{"type": "ai_off"}]
    assert browser.get("/api/ask/ai").json() == {"ai_on": False}


def test_a_model_failing_before_writing_anything_counts_as_ai_off(browser, shop, monkeypatch):
    monkeypatch.setattr(llm, "is_on", lambda model=None: True)

    def broken(*args, **kwargs):
        raise llm.ModelFailed("timed out")
        yield  # a generator, like the real one

    monkeypatch.setattr(llm, "chat", broken)
    assert chat(browser, "what's going on?") == [{"type": "ai_off"}]


def test_logged_out_people_cannot_chat(browser):
    assert browser.post("/api/ask/chat", json={"question": "hi"}).status_code == 401
    assert browser.get("/api/ask/ai").status_code == 401


def test_staff_get_no_money_from_any_lookup(browser, shop, model):
    staff = staff_browser(browser)
    fake = model(looks_up(("sales_of", {"part": "oil filters", "period": "this_week"})), writes("5 sold."))
    result = done(chat(staff, "oil filters this week?"))
    assert "money" not in result["lookups"][0]["values"]
    assert all(number["unit"] != "money" for number in result["lookups"][0]["numbers"])
    assert MONEY_HIDDEN in fake.calls[0]["messages"][0]["content"]
    with SessionLocal() as db:
        words = shop_words(db, shop)
        for name, tool in TOOLS.items():
            arguments = {"part": "oil filter"} if tool.needs_part else {}
            content = for_the_model(look_up(db, shop, None, words, name, arguments), None)
            assert "money" not in content and "MAD" not in content, name


def test_each_shop_only_sees_its_own_data(browser, shop, model):
    other = create_other_shop()
    other_oil = new_part(other.organization_id, "Oil filter", "Filters")
    sell(other.organization_id, other_oil, "Other Shop", days_ago=0, quantity=99)
    model(looks_up(("sales_of", {"part": "oil filters", "period": "this_week"})), writes("5."))
    assert done(chat(browser, "oil filters this week?"))["lookups"][0]["values"]["pieces"] == 5
    model(looks_up(("sales_of", {"part": "oil filters", "period": "this_week"})), writes("99."))
    other_owner = logged_in_browser("owner@other.ma", OWNER_PASSWORD)
    assert done(chat(other_owner, "oil filters this week?"))["lookups"][0]["values"]["pieces"] == 99


def test_asking_changes_nothing(browser, shop, model):
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(AuditLog))
    model(looks_up(("today_briefing", {}), ("part_details", {"part": "oil filter"})), writes("Fine."))
    chat(browser, "what's going on?")
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog)) == before


# The new lookups (today's shop: the oil filters and brake pads of tests/test_ask.py, "today" = LAST_DAY)

def lookup(shop_id, name: str, currency: str | None = "MAD", **arguments):
    with SessionLocal() as db:
        found = look_up(db, shop_id, currency, shop_words(db, shop_id), name, arguments)
        assert found.problem is None, found.problem
        return found.answer


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


def test_filters_are_matched_to_the_shops_own_names(shop):
    with SessionLocal() as db:
        found = look_up(db, shop, "MAD", shop_words(db, shop), "sales_of", {"branch": "rabat", "category": "brakes", "colour": "red"})
    assert found.filters == {"branch": RABAT, "category": "Brakes"}
    with SessionLocal() as db:
        assert "period must be one of" in look_up(db, shop, "MAD", shop_words(db, shop), "sales_of", {"period": "next_year"}).problem


# The number check

@pytest.mark.parametrize("written", [
    "1234", "1,234", "1 234", "1 234", "1.234,5", "1,234.5", "١٢٣٤", "12%", "about 1,200", "down 79%", "BP-1042", "21 October 2026",
])
def test_allowed_numbers_in_their_usual_forms(written):
    allowed = AllowedNumbers([{"value": 1234.5, "other": 1234, "before": 5900, "sku": "BP-1042", "day": "2026-10-21", "share": 12}], [])
    assert allowed.wrong_numbers(written) == []


@pytest.mark.parametrize("written", ["1235", "13 pieces", "about 2,000", "up 80%", "seventy"])
def test_numbers_that_dont_come_from_the_data_fail(written):
    assert AllowedNumbers([{"value": 1234, "before": 5900, "sku": "BP-1042"}], []).wrong_numbers(written) != []


def test_pieces_of_dates_and_part_numbers_are_not_added_up():
    allowed = AllowedNumbers([{"pieces": 5, "day": "2026-10-21", "sku": "BP-1042"}], [])
    assert allowed.wrong_numbers("21 October, BP-1042, 5 pieces") == []
    assert allowed.wrong_numbers("31 pieces") == ["31"]  # 10 + 21 from the date: not a fact


def test_list_markers_are_not_numbers():
    assert numbers_written("Top parts:\n1. Oil filter\n2. Brake pads") == []


def test_number_words_in_four_languages():
    assert numbers_in_words("twenty-five parts") == ["25"]
    assert numbers_in_words("quatre-vingt pièces") == ["80"]
    assert numbers_in_words("خمسة وعشرون قطعة") == ["25"]
    assert numbers_in_words("jouj dyal les pièces") == ["2"]
    assert numbers_in_words("rien de neuf, this one") == []


def test_checked_text_lets_out_whole_sentences_and_stops_at_the_first_wrong_number():
    text = CheckedText(AllowedNumbers([{"pieces": 5}], []))
    assert text.add("We sold 5") == ""
    assert text.add(" filters. And 6") == "We sold 5 filters."
    assert text.add(" more. Fine.") == ""
    assert text.wrong == ["6"]
    assert text.finish() == ""
    assert text.shown == "We sold 5 filters."


# The keyword rule (used when AI is off) no longer trips on apostrophes

def test_whats_is_not_read_as_a_part_called_s():
    shop_names = ShopWords(categories=("Brakes",), branches=(RABAT,), part_words=frozenset())
    assert read_with_rule("What's running out?", shop_names).type == "running_out"
    assert read_with_rule("What's going on today?", shop_names).part == "going"
