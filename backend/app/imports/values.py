"""Turns messy spreadsheet cells into clean values: text, whole numbers, money, dates.

Each function returns None for an empty cell and raises ValueProblem with a plain message
when the cell can't be understood.
"""

import re
import unicodedata
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any


class ValueProblem(Exception):
    """A cell that can't be used. The message is shown to the person as is."""


_CURRENCY = re.compile(r"(?i)mad|dhs?|eur|usd|[€$]")
_SPACES = re.compile(r"[\s  ']+")


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = " ".join(str(value).split())
    return text or None


def clean_sku(value: Any) -> str | None:
    text = clean_text(value)
    return text.upper() if text else None


def normalize_header(header: str) -> str:
    """'  Prix de Vente ' and 'prix de vente' match. Accents are ignored: 'Qté' == 'qte'."""
    without_accents = unicodedata.normalize("NFKD", header).encode("ascii", "ignore").decode()
    return " ".join(without_accents.lower().split())


def parse_number(value: Any, label: str) -> Decimal | None:
    """Understands 12,50 / 12.50 / 1 234,50 / 1.234,50 / 1,234.50 / '12,50 DH'."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    text = _SPACES.sub("", _CURRENCY.sub("", str(value)))
    if not text:
        return None
    if "," in text and "." in text:
        decimal_mark = "," if text.rfind(",") > text.rfind(".") else "."
        thousands_mark = "." if decimal_mark == "," else ","
        text = text.replace(thousands_mark, "").replace(decimal_mark, ".")
    elif text.count(",") == 1:
        text = text.replace(",", ".")
    elif text.count(",") > 1 or text.count(".") > 1:
        text = text.replace(",", "").replace(".", "")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueProblem(f"{label} is not a number") from None


def parse_whole_number(value: Any, label: str, allow_negative: bool = False) -> int | None:
    number = parse_number(value, label)
    if number is None:
        return None
    if number != number.to_integral_value():
        raise ValueProblem(f"{label} must be a whole number")
    if number < 0 and not allow_negative:
        raise ValueProblem(f"{label} can't be negative")
    return int(number)


def parse_money(value: Any, label: str) -> int | None:
    """Returns centimes: '12,50' -> 1250."""
    number = parse_number(value, label)
    if number is None:
        return None
    if number < 0:
        raise ValueProblem(f"{label} can't be negative")
    return int((number * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y", "%Y/%m/%d")


def parse_date(value: Any, label: str = "Date") -> date | None:
    """Day first, as written in Morocco and France: 15/03/2026."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = clean_text(value)
    if not text:
        return None
    first_part = text.split(" ")[0].split("T")[0]
    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(first_part, date_format).date()
        except ValueError:
            continue
    raise ValueProblem(f"{label} is not valid (use day/month/year, e.g. 15/03/2026)")


def show_cell(value: Any) -> str:
    """How a cell looks in the column-matching preview."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return clean_text(value) or ""
