"""The online assistant: Groq thinks and calls the app's read-only tools, every number in its answer is
checked against the tool results, money never reaches staff, each shop only sees its own data, and any
Groq failure gives one "online_off" line followed by the app's own answer.

Groq is a scripted fake here (tests never reach it): these tests check the app around it. The quality of
the real model's answers is measured by app/ask/check_real_assistant.py on 50 questions.
"""

import io
import json
import urllib.error
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select, update

from app.ai import groq, llm
from app.ask.data_tools import run_tool, tool_specs
from app.ask.data_tools.context import Asker
from app.ask.tool_numbers import allowed_numbers, unknown_numbers
from app.db import SessionLocal
from app.models import AskedQuestion, AuditLog, Organization, SaleLine, StockOut
from tests.helpers import OWNER_PASSWORD, create_other_shop, logged_in_browser, set_up_shop
from tests.test_ask import (  # noqa: F401  (shop is a fixture)
    LAST_DAY, MAIN, RABAT, branch_named, new_part, sell, shelve, shop, shop_named, staff_browser,
)


class FakeGroq:
    """Scripted replies: a reply is ("tools", [(name, args), ...]) or ("text", "the answer"). Remembers
    every conversation it was sent."""

    def __init__(self, replies: list):
        self.replies = list(replies)
        self.sent: list[dict] = []

    def complete(self, messages, tools, model=None):
        self.sent.append({"messages": json.loads(json.dumps(messages)), "tools": tools})
        kind, content = self.replies.pop(0)
        if kind == "fail":
            raise groq.GroqFailed(content)
        if kind == "tools":
            calls = [{"id": f"call{index}", "type": "function",
                      "function": {"name": name, "arguments": json.dumps(args)}} for index, (name, args) in enumerate(content)]
            return groq.Reply({"content": "", "tool_calls": calls}, 1000)
        return groq.Reply({"content": content}, 500)


@pytest.fixture
def online(monkeypatch):
    """online([...replies]) turns the online assistant on with a scripted Groq, the local model off."""
    monkeypatch.setattr(groq, "is_ready", lambda: True)
    monkeypatch.setattr(llm, "is_on", lambda model=None: False)

    def install(replies):
        fake = FakeGroq(replies)
        monkeypatch.setattr(groq, "complete", fake.complete)
        return fake

    return install


def chat(browser, question: str, earlier_turns: int = 0) -> list[dict]:
    response = browser.post("/api/ask/chat", json={"question": question, "earlier_turns": earlier_turns})
    assert response.status_code == 200, response.text
    return [json.loads(line) for line in response.text.splitlines() if line]


def done(events: list[dict]) -> dict:
    assert events[-1]["type"] == "done", events
    return events[-1]


OIL_THIS_WEEK = {"type": "Oil filter", "date_from": (LAST_DAY - timedelta(days=6)).isoformat(), "date_to": LAST_DAY.isoformat()}


# Answering with the tools

def test_the_model_calls_tools_and_its_checked_answer_is_shown(browser, shop, online):
    fake = online([("tools", [("sales", OIL_THIS_WEEK)]), ("text", "You sold 5 oil filters this week.")])
    events = chat(browser, "How many oil filters did we sell this week?")
    result = done(events)
    assert events[0] == {"type": "looking_up", "tool": "sales", "filters": {
        "type": "Oil filter", "range": f"{OIL_THIS_WEEK['date_from']}/{OIL_THIS_WEEK['date_to']}"}}
    assert result["text"] == "You sold 5 oil filters this week." and result["written_by"] == "groq"
    assert result["lookups"][0]["numbers"][0] == {"label": "Pieces sold", "value": 5, "unit": "pieces",
                                                  "key": "pieces_sold", "about": None}
    tool_reply = fake.sent[1]["messages"][-1]
    assert tool_reply["role"] == "tool" and json.loads(tool_reply["content"])["pieces"] == 5
    assert result["tokens"] == 1500


def test_the_instructions_give_today_the_last_sale_and_the_branches_with_sales(browser, shop, online):
    fake = online([("text", "Hello.")])
    chat(browser, "hello")
    instructions = fake.sent[0]["messages"][0]["content"]
    assert f"The newest sale imported is from {LAST_DAY.isoformat()}" in instructions
    assert "Today is" in instructions and MAIN in instructions and RABAT in instructions


def test_a_number_no_tool_gave_is_sent_back_once_then_the_fixed_answer_is_shown(browser, shop, online):
    fake = online([("tools", [("sales", OIL_THIS_WEEK)]), ("text", "You sold 7 oil filters."), ("text", "You sold 5 oil filters.")])
    result = done(chat(browser, "How many oil filters did we sell this week?"))
    assert result["text"] == "You sold 5 oil filters." and result["retried"] is True
    assert "7" in fake.sent[-1]["messages"][-1]["content"], "the model is told which number was wrong"


def test_a_number_still_wrong_after_the_second_try_gives_the_apps_own_answer(browser, shop, online):
    online([("tools", [("sales", OIL_THIS_WEEK)]), ("text", "You sold 7."), ("text", "Still 7.")])
    events = chat(browser, "How many oil filters did we sell this week?")
    assert {"type": "online_off", "reason": "unchecked"} in events
    assert events[-1] == {"type": "ai_off"}, "local model off too: the page asks the keyword rule"
    assert not any(event["type"] == "text" for event in events), "the unchecked answer is never shown"


@pytest.mark.parametrize("reason", ["offline", "daily_limit", "busy"])
def test_groq_failing_says_so_in_one_line_then_the_app_answers(browser, shop, online, monkeypatch, reason):
    online([("fail", reason)])
    monkeypatch.setattr(llm, "is_on", lambda model=None: True)
    monkeypatch.setattr(llm, "ask_json", lambda *args, **kwargs: None)
    events = chat(browser, "stock of oil filter")
    assert events[0] == {"type": "online_off", "reason": reason}
    assert done(events)["written_by"] == "app"


def test_the_owners_switch_off_sends_nothing_to_groq(browser, shop, online):
    fake = online([("text", "never")])
    with SessionLocal() as db:
        db.execute(update(Organization).values(online_assistant_on=False))
        db.commit()
    assert chat(browser, "stock of oil filter") == [{"type": "ai_off"}]
    assert fake.sent == []
    assert browser.get("/api/ask/ai").json() == {"ai_on": False, "online": False}


def test_a_follow_up_sends_the_conversation_and_its_numbers_stay_allowed(browser, shop, online):
    online([("tools", [("sales", OIL_THIS_WEEK)]), ("text", "5 oil filters.")])
    chat(browser, "How many oil filters this week?")
    fake = online([("text", "Yes, the 5 oil filters were all this week.")])
    result = done(chat(browser, "Are you sure?", earlier_turns=1))
    messages = fake.sent[0]["messages"]
    assert messages[1] == {"role": "user", "content": "How many oil filters this week?"}
    assert messages[2]["content"].startswith("5 oil filters.") and '"pieces":5' in messages[2]["content"]
    assert result["text"].startswith("Yes, the 5")


def test_staff_never_get_money_or_the_prices_tool(browser, shop, online):
    staff = staff_browser(browser)
    fake = online([("tools", [("sales", OIL_THIS_WEEK), ("prices", {"type": "Oil filter"})]), ("text", "5 sold.")])
    result = done(chat(staff, "oil filters sold this week and their price?"))
    assert "prices" not in {tool["function"]["name"] for tool in fake.sent[0]["tools"]}
    tool_results = " ".join(message["content"] for message in fake.sent[1]["messages"] if message["role"] == "tool")
    assert "value" not in tool_results and "margin" not in tool_results and "pieces" in tool_results
    assert json.loads(fake.sent[1]["messages"][-1]["content"]) == {"error": "Unknown tool 'prices'."}
    assert "must not see money" in fake.sent[0]["messages"][0]["content"]
    assert all(number["unit"] != "money" for lookup in result["lookups"] for number in lookup["numbers"])


def test_each_shop_only_sees_its_own_data(browser, shop, online):
    other = create_other_shop()
    sell(other.organization_id, new_part(other.organization_id, "Oil filter", "Filters"), "Other Shop", days_ago=0, quantity=99)
    online([("tools", [("sales", OIL_THIS_WEEK)]), ("text", "5.")])
    assert done(chat(browser, "oil filters this week?"))["lookups"][0]["numbers"][0]["value"] == 5
    online([("tools", [("sales", OIL_THIS_WEEK)]), ("text", "99.")])
    other_owner = logged_in_browser("owner@other.ma", OWNER_PASSWORD)
    assert done(chat(other_owner, "oil filters this week?"))["lookups"][0]["numbers"][0]["value"] == 99


def test_asking_changes_no_business_data_and_is_kept_in_history(browser, shop, online):
    with SessionLocal() as db:
        audit, sales = db.scalar(select(func.count()).select_from(AuditLog)), db.scalar(select(func.count()).select_from(SaleLine))
    online([("tools", [("sales", OIL_THIS_WEEK), ("stock", {"type": "Oil filter"})]), ("text", "5 sold.")])
    chat(browser, "oil filters?")
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog)) == audit
        assert db.scalar(select(func.count()).select_from(SaleLine)) == sales
        saved = db.scalar(select(AskedQuestion))
        assert saved.kind == "assistant" and saved.answer["tokens"] == 1500 and saved.answer["facts"][0]["pieces"] == 5


def test_the_tools_run_in_a_read_only_transaction(shop):
    from app.ask import online_assistant

    class Refuse(Exception):
        pass

    with SessionLocal() as db:
        def complete(messages, tools, model=None):
            db.execute(update(Organization).values(name="hacked"))  # what a broken tool would do
            raise Refuse

        original = groq.complete
        groq.complete = complete
        try:
            with pytest.raises(Exception) as error:
                list(online_assistant.answer(db, shop, "MAD", "hi", [], "en", LAST_DAY))
            assert "read-only" in str(error.value)
        finally:
            groq.complete = original


# The tools themselves

def asker(organization_id, currency: str | None = "MAD", db=None) -> Asker:
    return Asker(db, organization_id, LAST_DAY + timedelta(days=5), LAST_DAY, currency)


@pytest.fixture
def cars_shop(browser):
    set_up_shop(browser)
    shop_id = shop_named(MAIN)
    for name, quantity in (("Filtre à huile - Dacia Logan", 55), ("Filtre à air - Dacia Logan", 500),
                           ("Plaquettes de frein avant - Dacia Logan", 500), ("Filtre à huile - Renault Clio", 500),
                           ("Disques de frein avant (paire) - Dacia Logan", 20)):
        shelve(shop_id, new_part(shop_id, name, "Filters"), RABAT, quantity)
    return shop_id


@pytest.mark.parametrize(("args", "pieces"), [
    ({"type": "filtres à huile", "car": "Dacia Logan"}, 55),
    ({"type": "Filtre a huile", "car": "logan"}, 55),
    ({"type": "disques frein avant", "car": "Logan"}, 20),
    ({"type": "oil filter", "car": "Logan"}, 55),
    ({"car": "Dacia Logan"}, 1075),
])
def test_a_part_must_match_every_field_given(cars_shop, args, pieces):
    with SessionLocal() as db:
        assert run_tool(asker(cars_shop, db=db), "stock", {**args, "branch": "Rabat"}).data["pieces"] == pieces


def test_a_wrong_field_or_branch_gets_an_error_the_model_can_fix(cars_shop):
    with SessionLocal() as db:
        assert run_tool(asker(cars_shop, db=db), "stock", {"type": "pneu"}).data["error"] == "No part has the type 'pneu'."
        assert run_tool(asker(cars_shop, db=db), "stock", {"branch": "Fes"}).data["branches"] == [MAIN, RABAT] \
            or set(run_tool(asker(cars_shop, db=db), "stock", {"branch": "Fes"}).data["branches"]) == {MAIN, RABAT}
        assert run_tool(asker(cars_shop, db=db), "drop_table", {}).data == {"error": "Unknown tool 'drop_table'."}


def test_sales_compare_gives_changes_stock_outs_and_last_year(shop):
    oil = next(iter(db_ids(shop, "Oil filter")))
    sell(shop, oil, MAIN, days_ago=365, quantity=8)
    with SessionLocal() as db:
        db.add(StockOut(organization_id=shop, part_id=oil, branch_id=branch_named(shop, MAIN),
                        first_day=LAST_DAY - timedelta(days=3), last_day=LAST_DAY))
        db.commit()
        data = run_tool(asker(shop, db=db), "sales", {**OIL_THIS_WEEK, "compare": "previous_period"}).data
    assert data["pieces"] == 5 and data["compared_with"]["pieces"] == 0 and data["compared_with"]["change_pieces"] == 5
    assert data["stock_out_days"] == 4 and data["same_dates_last_year"]["pieces"] == 8


def test_a_period_past_the_last_sale_is_counted_up_to_it(shop):
    with SessionLocal() as db:
        data = run_tool(asker(shop, db=db), "sales", {"date_from": (LAST_DAY - timedelta(days=6)).isoformat(),
                                                      "date_to": (LAST_DAY + timedelta(days=5)).isoformat()}).data
    assert data["period"][1] == LAST_DAY.isoformat() and "imported up to" in data["note"]


def test_no_dates_means_the_30_days_up_to_the_last_sale(shop):
    with SessionLocal() as db:
        data = run_tool(asker(shop, db=db), "sales", {}).data
    assert data["period"] == [(LAST_DAY - timedelta(days=29)).isoformat(), LAST_DAY.isoformat()]
    assert "part_references" not in data, "no part asked: no count of parts that could be read as sales"


def test_staff_tools_have_no_money_fields(shop):
    with SessionLocal() as db:
        for name, args in (("sales", OIL_THIS_WEEK), ("stock", {}), ("stock", {"only": "dead"})):
            text = json.dumps(run_tool(asker(shop, None, db), name, args).data)
            assert "value" not in text and "margin" not in text and "cost" not in text
    assert "prices" not in {tool["function"]["name"] for tool in tool_specs(False)}


def db_ids(organization_id, name: str) -> set:
    from app.models import Part
    with SessionLocal() as db:
        return set(db.scalars(select(Part.id).where(Part.organization_id == organization_id, Part.name == name)))


# The number check

def test_numbers_from_tools_roundings_dates_and_the_question_are_allowed():
    allowed = allowed_numbers([{"pieces": 6513, "period": ["2026-10-01", "2026-10-31"], "change_percent": -9}],
                              ["top 5 parts?"], [date(2026, 11, 8)])
    assert unknown_numbers("About 6 500 pieces (6 513), down 9 % from 1 to 31 October 2026; top 5; 8 Nov.", allowed) == []
    assert unknown_numbers("You sold 6 281 pieces, 12 % more.", allowed) == ["6 281", "12"]
    assert unknown_numbers("Les cinq premières pièces", allowed) == []
    assert unknown_numbers("sept pièces", allowed) == ["7"]


# Groq's client

def refusal(code: int, body: str, headers: dict | None = None):
    return urllib.error.HTTPError(groq.URL, code, "refused", headers or {}, io.BytesIO(body.encode()))


def test_groq_out_of_daily_allowance_is_named(monkeypatch):
    def urlopen(request, timeout):
        raise refusal(429, "Rate limit reached on tokens per day (TPD): Limit 200000")
    monkeypatch.setattr(groq, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(groq.urllib.request, "urlopen", urlopen)
    with pytest.raises(groq.GroqFailed) as failure:
        groq.complete([], [])
    assert failure.value.reason == "daily_limit"


def test_groq_busy_this_minute_is_waited_for_once(monkeypatch):
    calls, waits = [], []

    class Response(io.BytesIO):
        headers = {"x-ratelimit-remaining-requests": "990", "x-ratelimit-limit-requests": "1000"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def urlopen(request, timeout):
        calls.append({**json.loads(request.data), "agent": request.get_header("User-agent")})
        if len(calls) == 1:
            raise refusal(429, "tokens per minute (TPM)", {"retry-after": "2"})
        return Response(json.dumps({"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 42}}).encode())

    monkeypatch.setattr(groq, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(groq.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(groq.time, "sleep", waits.append)
    reply = groq.complete([{"role": "user", "content": "hi"}], [])
    assert reply.message["content"] == "ok" and reply.tokens == 42 and waits == [2.0]
    assert groq.last_limits["requests_left_today"] == 990
    assert calls[0]["reasoning_effort"] == "low" and calls[0]["model"] == groq.GROQ_MODEL
    assert calls[0]["agent"] == "AutoStock-AI/1.0", "Groq's firewall refuses Python's default name"


def test_groq_unreachable_is_offline(monkeypatch):
    def urlopen(request, timeout):
        raise OSError("no internet")
    monkeypatch.setattr(groq, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(groq.urllib.request, "urlopen", urlopen)
    with pytest.raises(groq.GroqFailed) as failure:
        groq.complete([], [])
    assert failure.value.reason == "offline"


# Settings: the owner's switch and the allowance left

def test_settings_show_the_switch_and_the_allowance_left(browser, shop, online, monkeypatch):
    online([("tools", [("sales", OIL_THIS_WEEK)]), ("text", "5 sold.")])
    chat(browser, "oil filters?")
    settings = browser.get("/api/settings").json()
    assert settings["online_assistant_on"] is True and settings["groq_ready"] is True
    assert settings["groq_allowance"]["tokens_used_today"] == 1500 and settings["groq_allowance"]["answers_today"] == 1
    assert settings["groq_allowance"]["tokens_per_day"] == 200_000


def test_the_switch_is_audited_and_owner_only(browser, shop, online):
    assert browser.patch("/api/settings", json={"online_assistant_on": False}).json()["online_assistant_on"] is False
    with SessionLocal() as db:
        row = db.scalars(select(AuditLog).where(AuditLog.action == "organization.updated")).all()[-1]
    assert row.before["online_assistant_on"] is True and row.after["online_assistant_on"] is False
    assert staff_browser(browser).patch("/api/settings", json={"online_assistant_on": True}).status_code == 403


def test_the_online_assistant_cant_be_turned_on_without_a_key(browser, shop):
    browser.patch("/api/settings", json={"online_assistant_on": False})
    response = browser.patch("/api/settings", json={"online_assistant_on": True})
    assert response.status_code == 422 and "GROQ_API_KEY" in response.text
