import uuid
from dataclasses import dataclass
from datetime import date

KINDS = ("sales_spike", "sales_drop", "sold_at_zero", "stock_frozen", "negative_stock")
# "Needs action": the stock count is wrong somewhere. "Worth a look": sales changed a lot.
NEEDS_ACTION = "needs_action"
WORTH_A_LOOK = "worth_a_look"
SALES_KINDS = frozenset({"sales_spike", "sales_drop"})


def group_of(kind: str) -> str:
    return WORTH_A_LOOK if kind in SALES_KINDS else NEEDS_ACTION


@dataclass
class Problem:
    """Something worth a person's look, found on one day. Becomes an alert unless the daily limit or
    the no-repeat rule holds it back."""

    part_id: uuid.UUID
    branch_id: uuid.UUID
    kind: str
    started_on: date
    money_at_stake: int  # centimes
    sentence: str  # English for now; `numbers` lets the website rebuild it in another language
    numbers: dict

    @property
    def key(self) -> tuple[uuid.UUID, uuid.UUID, str]:
        return (self.part_id, self.branch_id, self.kind)

    @property
    def group(self) -> str:
        return group_of(self.kind)


def money(centimes: int, currency: str) -> str:
    return f"{round(centimes / 100):,} {currency}"


# What each kind's money clause says, after "About <money> ". Kept apart from the sentence itself
# (app/alerts/sales_rules.py, app/alerts/stock_rules.py) so staff can be shown the same alert
# without its money (see app/api/alerts.py, app/api/today.py).
MONEY_SUFFIX = {
    "sales_spike": "of sales above usual.",
    "sales_drop": "of sales below usual.",
    "sold_at_zero": "of stock not counted.",
    "stock_frozen": "of stock may be missing.",
    "negative_stock": "of stock to recount.",
}


def money_note(kind: str, at_stake: int, currency: str) -> str:
    return f"About {money(at_stake, currency)} {MONEY_SUFFIX[kind]}"


def day_label(day: date) -> str:
    return f"{day.day} {day:%b}"


def pieces(count: int) -> str:
    return f"{count} piece" if count == 1 else f"{count} pieces"
