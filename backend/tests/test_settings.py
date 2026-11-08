from tests.helpers import add_member, audit_rows, member_with_own_password, set_up_shop


def test_owner_reads_settings_with_mad_and_french_by_default(browser):
    set_up_shop(browser)

    assert browser.get("/api/settings").json() == {
        "name": "Atlas Parts", "currency": "MAD", "language": "fr", "online_assistant_on": True, "groq_ready": False, "groq_allowance": None,
    }


def test_owner_changes_settings_and_it_is_audited(browser):
    set_up_shop(browser)

    response = browser.patch("/api/settings", json={"name": "Atlas Parts Rabat", "currency": "EUR", "language": "ar"})

    assert response.json() == {
        "name": "Atlas Parts Rabat", "currency": "EUR", "language": "ar", "online_assistant_on": True, "groq_ready": False, "groq_allowance": None,
    }
    assert browser.get("/api/auth/me").json()["organization"]["name"] == "Atlas Parts Rabat"
    row = audit_rows("organization.updated")[-1]
    assert row.before == {"name": "Atlas Parts", "currency": "MAD", "language": "fr", "online_assistant_on": True}
    assert row.after == {"name": "Atlas Parts Rabat", "currency": "EUR", "language": "ar", "online_assistant_on": True}


def test_saving_without_changes_writes_no_audit_row(browser):
    set_up_shop(browser)

    browser.patch("/api/settings", json={"name": "Atlas Parts", "currency": "MAD"})

    assert audit_rows("organization.updated") == []


def test_only_owners_change_settings(browser):
    set_up_shop(browser)
    add_member(browser, "manager@shop.ma", "manager")
    add_member(browser, "staff@shop.ma", "staff")

    for email in ["manager@shop.ma", "staff@shop.ma"]:
        member = member_with_own_password(email)
        assert member.get("/api/settings").status_code == 403
        assert member.patch("/api/settings", json={"name": "Taken over"}).status_code == 403

    assert browser.get("/api/settings").json()["name"] == "Atlas Parts"


def test_unknown_currency_and_empty_name_are_rejected(browser):
    set_up_shop(browser)

    assert browser.patch("/api/settings", json={"currency": "BTC"}).status_code == 422
    assert browser.patch("/api/settings", json={"language": "de"}).status_code == 422
    assert browser.patch("/api/settings", json={"name": "   "}).status_code == 422
