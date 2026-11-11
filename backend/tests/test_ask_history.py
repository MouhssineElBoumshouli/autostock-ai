"""Each person's last questions on the Ask page are kept on the server (newest 20), shown when they
come back, never to anyone else, and forgotten only on "Clear history". Also: "et le mois dernier ?"
after the briefing answers about last month."""

import json

import pytest
from sqlalchemy import select

from app.ai import llm
from app.ask import history
from app.db import SessionLocal
from app.models import AuditLog
from tests.helpers import OWNER_PASSWORD, create_other_shop, logged_in_browser
from tests.test_ask import shop, staff_browser  # noqa: F401  (shop is a fixture)


def chat(browser, question: str, previous: dict | None = None) -> dict:
    response = browser.post("/api/ask/chat", json={"question": question, "previous": previous})
    assert response.status_code == 200, response.text
    return [json.loads(line) for line in response.text.splitlines() if line][-1]


def test_questions_and_answers_are_kept_and_shown_again(browser, shop, monkeypatch):
    monkeypatch.setattr(llm, "is_on", lambda model=None: True)
    done = chat(browser, "how many oil filters did we sell this week?")
    browser.post("/api/ask", json={"question": "what is running out?"})  # AI off: the keyword rule's answer
    kept = browser.get("/api/ask/history").json()
    assert [(entry["question"], entry["kind"]) for entry in kept] == [
        ("how many oil filters did we sell this week?", "assistant"), ("what is running out?", "rule")]
    assert kept[0]["answer"]["text"] == done["text"] and kept[1]["answer"]["answer"]


def test_only_the_newest_are_kept(browser, shop, monkeypatch):
    assert history.KEPT_PER_PERSON == 20
    monkeypatch.setattr(history, "KEPT_PER_PERSON", 3)
    for number in range(5):
        browser.post("/api/ask", json={"question": f"stock of oil filters {number}"})
    assert [entry["question"] for entry in browser.get("/api/ask/history").json()] == [
        "stock of oil filters 2", "stock of oil filters 3", "stock of oil filters 4"]


def test_each_person_sees_only_their_own_questions(browser, shop):
    browser.post("/api/ask", json={"question": "what should I order?"})
    staff = staff_browser(browser)
    assert staff.get("/api/ask/history").json() == []
    create_other_shop()
    assert logged_in_browser("owner@other.ma", OWNER_PASSWORD).get("/api/ask/history").json() == []


def test_clear_history_forgets_them(browser, shop):
    browser.post("/api/ask", json={"question": "what should I order?"})
    assert browser.delete("/api/ask/history").status_code == 204
    assert browser.get("/api/ask/history").json() == []


def test_logged_out_people_have_no_history(browser):
    assert browser.get("/api/ask/history").status_code == 401


def test_and_last_month_after_the_briefing_is_about_last_month(browser, shop, monkeypatch):
    monkeypatch.setattr(llm, "is_on", lambda model=None: True)
    briefing = chat(browser, "Quoi de neuf ?")
    assert briefing["question"] == {"type": "today_briefing", "filters": {}}
    follow_up = chat(browser, "Et le mois dernier ?", briefing["question"])
    assert follow_up["question"] == {"type": "today_briefing", "filters": {"period": "last_month"}}
    assert follow_up["text"].startswith("Le mois dernier (1 août – 31 août) :")
    assert follow_up["lookups"][0]["values"]["sales_in_period"]["period"] == "last_month"
