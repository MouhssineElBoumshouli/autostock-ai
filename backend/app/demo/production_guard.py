"""A real shop must never get demo data by mistake: on a shop's computer (APP_ENV=production) the
demo commands stop, unless the person adds --yes-demo-in-production on purpose."""

import sys

from app.config import IS_PRODUCTION

YES_FLAG = "--yes-demo-in-production"
REFUSED = (
    "Stopped: this is a real shop's computer (APP_ENV=production), so no demo data is added here.\n"
    f"To add the made-up demo shop anyway (it is kept apart from the real shop), run the same command with {YES_FLAG}."
)


def refuse_demo_in_production(args: list[str] | None = None) -> None:
    args = sys.argv[1:] if args is None else args
    if IS_PRODUCTION and YES_FLAG not in args:
        sys.exit(REFUSED)
