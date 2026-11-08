"""The two kinds of file and the fields a column can be matched to."""

from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException

ImportKind = Literal["parts", "sales", "equivalents"]


@dataclass(frozen=True)
class Field:
    key: str
    label: str  # used in problem messages, e.g. "Quantity is not a number"
    required: bool = False


FIELDS: dict[str, list[Field]] = {
    "parts": [
        Field("sku", "SKU", required=True),
        Field("name", "Name", required=True),
        Field("brand", "Brand"),
        Field("category", "Category"),
        Field("oem_reference", "OEM reference"),
        Field("unit_cost", "Unit cost"),
        Field("sale_price", "Sale price"),
        Field("min_stock", "Minimum stock"),
        Field("pack_size", "Pack size"),
        Field("quantity", "Quantity"),
        Field("branch", "Branch"),
        Field("supplier", "Supplier"),
        Field("delivery_days", "Delivery time"),  # set on the part's supplier, not on the part
    ],
    "sales": [
        Field("date", "Date", required=True),
        Field("sku", "SKU", required=True),
        Field("quantity", "Quantity", required=True),
        Field("unit_price", "Unit price"),
        Field("branch", "Branch"),
    ],
    "equivalents": [
        Field("our_code", "Our code", required=True),
        Field("equivalent_code", "Equivalent code", required=True),
    ],
}


# Column headers for the "parts" and "sales" sheets of the data export, and the sample files on
# the Stock > Import screen, in each language. Copied from frontend/src/i18n/{en,fr,ar}.ts
# (importFile.fieldNames), which is where these words are normally kept (CLAUDE.md), because this
# text is written by the server (an exported file has no browser to translate it in): the same
# exception the Ask answers already use. Every one of these is also recognised by suggest_field()
# without help (tests/test_export_labels.py), in whichever of the three languages the file is read
# back in, so a shop's own export always re-imports cleanly.
FIELD_LABELS: dict[str, dict[ImportKind, dict[str, str]]] = {
    "en": {
        "parts": {
            "sku": "SKU", "name": "Name", "brand": "Brand", "category": "Category",
            "oem_reference": "OEM reference", "unit_cost": "Unit cost", "sale_price": "Sale price",
            "min_stock": "Minimum stock", "pack_size": "Pack size", "quantity": "Quantity in stock",
            "branch": "Branch", "supplier": "Supplier", "delivery_days": "Delivery time (days)",
        },
        "sales": {"date": "Date", "sku": "SKU", "quantity": "Quantity sold", "unit_price": "Unit price", "branch": "Branch"},
    },
    "fr": {
        "parts": {
            "sku": "Référence", "name": "Désignation", "brand": "Marque", "category": "Famille",
            "oem_reference": "Référence OEM", "unit_cost": "Prix d’achat", "sale_price": "Prix de vente",
            "min_stock": "Stock minimum", "pack_size": "Conditionnement", "quantity": "Quantité en stock",
            "branch": "Succursale", "supplier": "Fournisseur", "delivery_days": "Délai de livraison (jours)",
        },
        "sales": {
            "date": "Date", "sku": "Référence", "quantity": "Quantité vendue", "unit_price": "Prix unitaire",
            "branch": "Succursale",
        },
    },
    "ar": {
        "parts": {
            "sku": "المرجع", "name": "الاسم", "brand": "العلامة", "category": "الفئة",
            "oem_reference": "مرجع OEM", "unit_cost": "سعر الشراء", "sale_price": "سعر البيع",
            "min_stock": "الحد الأدنى للمخزون", "pack_size": "حجم العبوة", "quantity": "الكمية في المخزون",
            "branch": "الفرع", "supplier": "المورد", "delivery_days": "مدة التوصيل (أيام)",
        },
        "sales": {
            "date": "التاريخ", "sku": "المرجع", "quantity": "الكمية المبيعة", "unit_price": "سعر الوحدة",
            "branch": "الفرع",
        },
    },
}


def field_labels(language: str, kind: ImportKind) -> dict[str, str]:
    return FIELD_LABELS.get(language, FIELD_LABELS["en"])[kind]


def check_mapping(kind: ImportKind, mapping: dict[int, str], column_count: int) -> dict[str, int]:
    """Validates "column index -> field" and returns "field -> column index"."""
    known = {field.key for field in FIELDS[kind]}
    by_field: dict[str, int] = {}
    for column, field in mapping.items():
        if field not in known or not 0 <= column < column_count:
            raise HTTPException(422, "The column matching doesn't fit this file. Upload it again.")
        if field in by_field:
            label = next(f.label for f in FIELDS[kind] if f.key == field)
            raise HTTPException(422, f"{label} is chosen for two columns. Choose it for one column only.")
        by_field[field] = column
    missing = [field.label for field in FIELDS[kind] if field.required and field.key not in by_field]
    if missing:
        raise HTTPException(422, f"Choose a column for: {', '.join(missing)}.")
    return by_field
