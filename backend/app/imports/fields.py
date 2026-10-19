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
