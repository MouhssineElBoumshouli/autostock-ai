from datetime import date, datetime

import pytest

from app.imports.values import (
    ValueProblem,
    clean_sku,
    clean_text,
    normalize_header,
    parse_date,
    parse_money,
    parse_whole_number,
)


@pytest.mark.parametrize(
    ("cell", "centimes"),
    [
        ("12,50", 1250),
        ("12.50", 1250),
        ("1 234,50", 123450),
        ("1 234,50", 123450),  # non-breaking space from French Excel
        ("1.234,50", 123450),
        ("1,234.50", 123450),
        ("1 650,00 DH", 165000),
        ("45,00dh", 4500),
        ("€ 9,99", 999),
        (320, 32000),
        (275.5, 27550),
        ("0,005", 1),  # rounds to the nearest centime
    ],
)
def test_money_in_many_formats(cell, centimes):
    assert parse_money(cell, "Sale price") == centimes


def test_empty_money_is_none():
    assert parse_money(None, "Sale price") is None
    assert parse_money("  ", "Sale price") is None


def test_money_problems():
    with pytest.raises(ValueProblem, match="Sale price is not a number"):
        parse_money("douze", "Sale price")
    with pytest.raises(ValueProblem, match="Sale price can't be negative"):
        parse_money("-45", "Sale price")


def test_whole_numbers():
    assert parse_whole_number("12", "Quantity") == 12
    assert parse_whole_number(" 1 200 ", "Quantity") == 1200
    assert parse_whole_number(7.0, "Quantity") == 7
    assert parse_whole_number("3,0", "Quantity") == 3
    with pytest.raises(ValueProblem, match="Quantity must be a whole number"):
        parse_whole_number("2,5", "Quantity")
    with pytest.raises(ValueProblem, match="Quantity is not a number"):
        parse_whole_number("douze", "Quantity")
    with pytest.raises(ValueProblem, match="Quantity can't be negative"):
        parse_whole_number("-3", "Quantity")


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("15/03/2026", date(2026, 3, 15)),
        ("15-03-2026", date(2026, 3, 15)),
        ("15.03.2026", date(2026, 3, 15)),
        ("2026-03-15", date(2026, 3, 15)),
        ("15/03/26", date(2026, 3, 15)),
        ("15/03/2026 10:30", date(2026, 3, 15)),
        (datetime(2026, 3, 15, 9, 0), date(2026, 3, 15)),
        (date(2026, 3, 15), date(2026, 3, 15)),
    ],
)
def test_dates_day_first(cell, expected):
    assert parse_date(cell) == expected


def test_bad_dates():
    for cell in ["31/02/2026", "03/15/2026", "hier"]:
        with pytest.raises(ValueProblem, match="Date is not valid"):
            parse_date(cell)


def test_text_and_sku_cleaning():
    assert clean_text("  Filtre   à huile ") == "Filtre à huile"
    assert clean_text("   ") is None
    assert clean_text(12345.0) == "12345"
    assert clean_sku(" bp-001 ") == "BP-001"


def test_headers_match_without_accents_case_or_spaces():
    assert normalize_header("  Qté en  Stock ") == normalize_header("qte en stock")
    assert normalize_header("Réf.") == "ref."
