"""Alembic runs this file to apply database changes (migrations)."""

from alembic import context

from app.db import Base, engine

target_metadata = Base.metadata


def run_migrations() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
