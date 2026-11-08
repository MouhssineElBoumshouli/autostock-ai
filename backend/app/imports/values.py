"""Turns messy spreadsheet cells into clean values: text, whole numbers, money, dates.

Each function returns None for an empty cell and raises ValueProblem with a plain message
when the cell can't be understood.
"""

import math
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


_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_NUMBERS = re.compile(r"\d+(?:[.,]\d+)?")
# How to turn one of each unit into days, checked in this order. Anything else is days ("5 j", "5 jours").
_UNITS = [
    (("sem", "week", "wk", "أسبوع", "اسبوع", "أسابيع"), lambda n: n * 7),
    (("mois", "month", "شهر", "أشهر"), lambda n: n * 30),
    (("heure", "hour", "ساعة", "ساعات"), lambda n: n / 24),
]
_HOURS = re.compile(r"\d\s*h\b")  # "48h", "48 h"
# Read before the units: "hors week-end" is not a week, Arabic says "two weeks" in one word.
_REWRITE = [("week-end", ""), ("weekend", ""), ("أسبوعين", "2 أسبوع"), ("اسبوعين", "2 أسبوع"), ("شهرين", "2 شهر")]
MOST_DELIVERY_DAYS = 365  # more than this is not a delivery time (a date read as a number, a price...)
NOT_DAYS = "Delivery time is not a number of days"


def parse_delivery_days(value: Any) -> int | None:
    """'5', '5 jours', '5j', '3-5 jours' (the longer one), '2 semaines', '1 mois', '48h', '١٠ أيام' -> days.
    A week or a month alone counts one of it. Raises ValueProblem when it isn't a delivery time."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (date, datetime)):
        raise ValueProblem(NOT_DAYS)
    if isinstance(value, (int, float, Decimal)):
        days = Decimal(str(value))
    else:
        text = (clean_text(value) or "").lower().translate(_DIGITS)
        for words, plain in _REWRITE:
            text = text.replace(words, plain)
        if not text:
            return None
        numbers = [Decimal(n.replace(",", ".")) for n in _NUMBERS.findall(text)]
        to_days = next((convert for words, convert in _UNITS if any(word in text for word in words)), None)
        if _HOURS.search(text):
            to_days = _UNITS[2][1]
        if not numbers and to_days is None:
            raise ValueProblem(NOT_DAYS)
        days = (to_days or (lambda n: n))(max(numbers, default=Decimal(1)))
    whole = math.ceil(days)
    if not 0 <= whole <= MOST_DELIVERY_DAYS:
        raise ValueProblem(NOT_DAYS)
    return whole


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
