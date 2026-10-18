"""Reads an uploaded .xlsx or .csv file into a header row and data rows."""

import csv
import io
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

MAX_FILE_BYTES = 10 * 1024 * 1024
# Above this, a file is more likely broken (wrong sheet, no filters) than a real parts or sales list.
MAX_ROWS = 20_000
UNREADABLE = "We couldn't read this file. Check that it opens in Excel, then try again."
TOO_MANY_ROWS = f"This file has more than {MAX_ROWS:,} rows. Split it into smaller files."


@dataclass
class Table:
    headers: list[str]
    # (row number as Excel shows it, cell values)
    rows: list[tuple[int, list[Any]]]


def read_table(content: bytes, file_name: str) -> Table:
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "The file is larger than 10 MB. Split it into smaller files.")
    lower = file_name.lower()
    if lower.endswith(".xlsx"):
        raw_rows = _xlsx_rows(content)
    elif lower.endswith(".csv"):
        raw_rows = _csv_rows(content)
    elif lower.endswith(".xls"):
        raise HTTPException(422, "This is an old Excel file (.xls). Open it in Excel and save it as .xlsx.")
    else:
        raise HTTPException(422, "Use an Excel file (.xlsx) or a CSV file (.csv).")
    table = _to_table(raw_rows)
    if len(table.rows) > MAX_ROWS:
        raise HTTPException(413, TOO_MANY_ROWS)
    return table


def _xlsx_rows(content: bytes) -> list[list[Any]]:
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheet = workbook.worksheets[0]
        rows = [list(row) for row in sheet.iter_rows(values_only=True)]
        workbook.close()
        return rows
    except Exception as error:  # openpyxl raises many kinds of errors for broken files
        raise HTTPException(422, UNREADABLE) from error


def _csv_rows(content: bytes) -> list[list[Any]]:
    # Excel in French saves CSV in Windows-1252 with ";" between columns; others use UTF-8 and ",".
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(422, UNREADABLE)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if text.split("\n", 1)[0].count(";") > 0 else ","
    return [row for row in csv.reader(io.StringIO(text), delimiter=delimiter)]


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _to_table(raw_rows: list[list[Any]]) -> Table:
    numbered = [(index + 1, row) for index, row in enumerate(raw_rows) if not all(_is_empty(v) for v in row)]
    if not numbered:
        raise HTTPException(422, "The file is empty.")

    # Files often start with a title line ("Inventaire au 15/10/2026"). The header is the first row
    # that is about as full as the fullest rows near the top.
    filled = [sum(not _is_empty(v) for v in row) for _, row in numbered[:20]]
    header_at = next(i for i, count in enumerate(filled) if count >= max(2, 0.6 * max(filled)) or count == max(filled))
    numbered = numbered[header_at:]
    _, header_row = numbered[0]
    width = max(len(row) for _, row in numbered)
    # Drop columns that are empty everywhere (Excel often adds some at the end).
    used = [i for i in range(width) if any(i < len(row) and not _is_empty(row[i]) for _, row in numbered)]
    headers = [
        " ".join(str(header_row[i]).split()) if i < len(header_row) and not _is_empty(header_row[i])
        else f"Column {get_column_letter(i + 1)}"
        for i in used
    ]
    rows = [(number, [row[i] if i < len(row) else None for i in used]) for number, row in numbered[1:]]
    if not rows:
        raise HTTPException(422, "The file has a header row but no data under it.")
    return Table(headers=headers, rows=rows)
