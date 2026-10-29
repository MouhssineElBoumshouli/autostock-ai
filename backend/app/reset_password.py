"""A forgotten password, from the shop computer (docs/INSTALL.md, "Forgotten password"):

    docker compose -f docker-compose.prod.yml exec app python -m app.reset_password owner@shop.ma

The new password is typed twice and never shown. Same rules as on the website. That person is
logged out everywhere, any login block on their email is lifted, and the Activity page shows it.
"""

import sys
from getpass import getpass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_change
from app.auth.emails import clean_email
from app.auth.login_limits import clear_failures
from app.auth.passwords import MIN_PASSWORD_LENGTH, check_password_rules, hash_password
from app.auth.sessions import end_all_sessions
from app.db import SessionLocal
from app.models import User


class ResetRefused(Exception):
    pass


def reset_password(db: Session, email: str, password: str) -> User:
    try:
        email = clean_email(email)
        check_password_rules(password)
    except HTTPException as refused:
        raise ResetRefused(refused.detail) from None
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    if user is None:
        raise ResetRefused(f"Nobody has the email {email}. Check the spelling (it is the email used to log in).")
    user.password_hash = hash_password(password)
    user.must_change_password = False
    end_all_sessions(db, user)
    clear_failures(db, email)
    record_change(db, user, "user.password_set_on_shop_computer", "user", user.id)
    db.commit()
    return user


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Say whose password to reset, for example: python -m app.reset_password owner@shop.ma")
    password = getpass(f"New password (at least {MIN_PASSWORD_LENGTH} characters, nothing is shown while you type): ")
    if getpass("Type it again: ") != password:
        sys.exit("The two passwords are not the same. Nothing was changed.")
    with SessionLocal() as db:
        try:
            user = reset_password(db, sys.argv[1], password)
        except ResetRefused as refused:
            sys.exit(f"Not changed: {refused}")
    print(f"Done. {user.name} can log in with the new password. They were logged out on every device.")


if __name__ == "__main__":
    main()
