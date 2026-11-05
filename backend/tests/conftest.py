"""Test setup: tests use their own database (<name>_test), emptied after every test."""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

real_url = make_url(os.environ["DATABASE_URL"])
test_url = real_url.set(database=f"{real_url.database}_test")
os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
# Tests never reach Groq, whatever .env says: the cloud writer is a scripted fake in them.
os.environ["GROQ_API_KEY"] = ""


def create_test_database() -> None:
    admin = create_engine(real_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        found = connection.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": test_url.database})
        if not found:
            connection.execute(text(f'CREATE DATABASE "{test_url.database}"'))
    admin.dispose()


create_test_database()

# Imported only now, so the app connects to the test database.
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.imports import jobs  # noqa: E402
from tests.helpers import new_browser  # noqa: E402

command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture(autouse=True)
def empty_tables():
    yield
    names = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {names} CASCADE"))


@pytest.fixture(autouse=True)
def imports_run_in_the_test(monkeypatch):
    """Import steps run here instead of in their own process, so a test sees them finished (and a
    small limit set by a test applies). test_import_jobs.py tests the real separate process."""
    monkeypatch.setattr(jobs, "run_apart", jobs.run_step)


@pytest.fixture
def browser():
    return new_browser()
