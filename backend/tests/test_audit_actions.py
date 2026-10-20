"""Every `record_change(...)` call's action name must be registered in `app.audit.KNOWN_ACTIONS`.

This is a static check, not a database one: it reads the source of every file under `app/` and
finds the action string literal passed as the third argument to `record_change`. If someone adds
a new kind of change without adding its name to KNOWN_ACTIONS, this test fails — a reminder to
also give it a plain sentence in `activitySentence.ts` and `i18n/en.ts`, so it never shows up on
the Activity page as a vague "made a change"."""

import ast
from pathlib import Path

from app.audit import KNOWN_ACTIONS

APP_DIR = Path(__file__).resolve().parent.parent / "app"


def _actions_recorded_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = set()
    for node in ast.walk(tree):
        is_record_change = isinstance(node, ast.Call) and (
            (isinstance(node.func, ast.Name) and node.func.id == "record_change")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "record_change")
        )
        if is_record_change and len(node.args) >= 3 and isinstance(node.args[2], ast.Constant):
            found.add(node.args[2].value)
    return found


def test_every_recorded_action_is_registered():
    found: set[str] = set()
    for path in APP_DIR.rglob("*.py"):
        found |= _actions_recorded_in(path)

    missing = found - KNOWN_ACTIONS
    unused = KNOWN_ACTIONS - found
    assert not missing, f"Add these to KNOWN_ACTIONS (app/audit.py) and give them a sentence on the Activity page: {missing}"
    assert not unused, f"These are in KNOWN_ACTIONS but no code records them anymore: {unused}"
