"""The sample files offered on the Import screen ("Start here" and empty states): a handful of
made-up rows, with the exact columns our own import screen understands, in the shop's language.
"""

from datetime import date, timedelta
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font

from app.imports.fields import ImportKind, field_labels

BOLD = Font(bold=True)

# sku, name, brand, category, oem_reference, unit_cost, sale_price, min_stock, pack_size, supplier, delivery_days, quantity
_SAMPLE_PARTS = [
    ("BP-001", "Front brake pads", "Bosch", "Brakes", "0986494525", 180, 320, 10, 1, "Auto Hall Pieces", 3, 6),
    ("FL-200", "Oil filter", "Mann-Filter", "Filtration", "W 712/95", 35.5, 65, 20, 5, "Distri Filtres", 2, 48),
    ("BT-912", "Battery 12V 70Ah", "Varta", "Electrical", "E13", 1250, 1650, 3, 1, "Varta Morocco", 15, 5),
    ("HL-900", "Engine oil 5W30 5L", "Total", "Lubricants", "QUARTZ 9000", 290, 420, 12, 4, "Total Morocco", 5, 35),
]

# date, sku, quantity, unit_price, branch
_SAMPLE_SALES = [
    (date.today() - timedelta(days=3), "BP-001", 2, 320, "Casablanca"),
    (date.today() - timedelta(days=2), "FL-200", 4, 65, "Casablanca"),
    (date.today() - timedelta(days=1), "HL-900", 3, 420, "Casablanca"),
    (date.today(), "BT-912", 1, 1650, "Rabat"),
]


def build_sample_file(kind: ImportKind, language: str) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    if kind == "parts":
        words = field_labels(language, "parts")
        _header(sheet, [words[k] for k in ("sku", "name", "brand", "category", "oem_reference", "unit_cost",
                                            "sale_price", "min_stock", "pack_size", "supplier", "delivery_days",
                                            "quantity")])
        for row in _SAMPLE_PARTS:
            sheet.append(row)
    elif kind == "sales":
        words = field_labels(language, "sales")
        _header(sheet, [words[k] for k in ("date", "sku", "quantity", "unit_price", "branch")])
        for row in _SAMPLE_SALES:
            sheet.append(row)
    else:
        raise ValueError(f"No sample file for {kind!r}.")

    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = max(len(str(c.value or "")) for c in column) + 2

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _header(sheet, texts: list[str]) -> None:
    sheet.append(texts)
    for cell in sheet[1]:
        cell.font = BOLD
