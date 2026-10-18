from datetime import timedelta

from app.auth.login_limits import is_blocked
from app.db import SessionLocal, utc_now
from app.models import LoginFailure

EMAIL = "someone@shop.ma"


def add_failures(minutes_ago: list[float]) -> None:
    now = utc_now()
    with SessionLocal() as db:
        for minutes in minutes_ago:
            db.add(LoginFailure(email=EMAIL, created_at=now - timedelta(minutes=minutes)))
        db.commit()


def blocked() -> bool:
    with SessionLocal() as db:
        return is_blocked(db, EMAIL)


def test_four_failures_do_not_block():
    add_failures([1, 2, 3, 4])
    assert not blocked()


def test_five_failures_within_15_minutes_block():
    add_failures([1, 2, 3, 4, 5])
    assert blocked()


def test_block_lasts_15_minutes_after_the_fifth_failure():
    add_failures([14, 15, 16, 17, 18])
    assert blocked()


def test_block_ends_after_15_minutes():
    add_failures([16, 17, 18, 19, 20])
    assert not blocked()


def test_failures_spread_over_more_than_15_minutes_do_not_block():
    add_failures([1, 5, 10, 15, 20])
    assert not blocked()


def test_other_emails_are_not_affected():
    add_failures([1, 2, 3, 4, 5])
    with SessionLocal() as db:
        assert not is_blocked(db, "other@shop.ma")
