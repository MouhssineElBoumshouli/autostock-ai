"""Reads an uploaded .xlsx or .csv file from disk, row by row, so a file of millions of lines never
sits in memory: a quick look at the top finds the header, then read() goes through every line."""

import codecs
import csv
import re
import zipfile
from collections.abc import Callable, Iterator
from contextlib import closing
from dataclasses import dataclass, field
from itertools import islice
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

MAX_FILE_BYTES = 500 * 1024 * 1024
# Above this, a file is more likely broken (wrong sheet, no filters) than a real parts or sales list.
MAX_ROWS = 2_200_000
LOOK_AT_ROWS = 1000  # rows read to find the header and the columns in use
REPORT_EVERY = 10_000
UNREADABLE = "We couldn't read this file. Check that it opens in Excel, then try again."
TOO_BIG = "The file is larger than 500 MB. Split it into smaller files."
ROW_TAG = re.compile(rb"<(?:\w+:)?row[ >]")


def too_many_rows() -> HTTPException:
    return HTTPException(413, f"This file has more than {MAX_ROWS:,} rows. Split it into smaller files.")


@dataclass
class Table:
    path: Path
    file_name: str
    headers: list[str]
    first_rows: list[list[Any]]  # the first data rows, for the preview
    row_count: int  # counted without reading the cells: the true count comes from read()
    columns_in_use: list[int]
    header_cells: list[str]
    header_row: int
    # Told how many rows were read so far, every REPORT_EVERY rows.
    on_progress: Callable[[int], None] | None = None
    # While reading a workbook with several sheets of rows: the sheet of the row just given.
    sheet: str | None = field(default=None, init=False)
    rows_read: int = field(default=0, init=False)

    def read(self) -> Iterator[tuple[int, list[Any]]]:
        """Every data row: (row number as Excel shows it, cells of the columns in use)."""
        columns = self.columns_in_use
        for number, row in self._raw_rows():
            if _row_is_empty(row):
                continue
            self.rows_read += 1
            if self.rows_read > MAX_ROWS:
                raise too_many_rows()
            if self.on_progress and self.rows_read % REPORT_EVERY == 0:
                self.on_progress(self.rows_read)
            width = len(row)
            yield number, [row[i] if i < width else None for i in columns]

    def _raw_rows(self) -> Iterator[tuple[int, Any]]:
        if self.path.suffix.lower() == ".csv":
            yield from islice(_csv_rows(self.path), self.header_row, None)
        else:
            yield from self._xlsx_data_rows()

    def _xlsx_data_rows(self) -> Iterator[tuple[int, Any]]:
        """The first sheet, then each later sheet starting with the same headers: Excel stops at
        1,048,576 rows on a sheet, so a longer history comes on several ("Ventes 1", "Ventes 2"...)."""
        with closing(_open_workbook(self.path)) as workbook:
            for index, sheet in enumerate(workbook.worksheets):
                rows = _sheet_rows(sheet)
                if index == 0:
                    rows = islice(rows, self.header_row, None)
                elif not _skip_to_same_headers(rows, self.header_cells):
                    continue
                self.sheet = sheet.title if len(workbook.worksheets) > 1 else None
                yield from rows


def open_table(path: Path, file_name: str) -> Table:
    """Looks at the top of a saved upload. Raises what the person should be told if it can't be used."""
    if path.stat().st_size > MAX_FILE_BYTES:
        raise HTTPException(413, TOO_BIG)
    lower = file_name.lower()
    if lower.endswith(".xlsx"):
        top = _first_rows(_xlsx_first_sheet(path))
        total = _count_xlsx_rows(path)
    elif lower.endswith(".csv"):
        top = _first_rows(_csv_rows(path))
        total = sum(1 for _, row in _csv_rows(path) if not _row_is_empty(row))
    elif lower.endswith(".xls"):
        raise HTTPException(422, "This is an old Excel file (.xls). Open it in Excel and save it as .xlsx.")
    else:
        raise HTTPException(422, "Use an Excel file (.xlsx) or a CSV file (.csv).")
    if total > MAX_ROWS:
        raise too_many_rows()
    return _to_table(path, file_name, top, total)


def saved_file_suffix(file_name: str) -> str:
    """How an upload is named on disk: only its type is kept from the person's file name."""
    return ".xlsx" if file_name.lower().endswith(".xlsx") else ".csv"


def _first_rows(rows: Iterator[tuple[int, Any]]) -> list[tuple[int, list[Any]]]:
    filled = ((number, list(row)) for number, row in rows if not _row_is_empty(row))
    return list(islice(filled, LOOK_AT_ROWS))


def _open_workbook(path: Path):
    try:
        return load_workbook(path, read_only=True, data_only=True)
    except Exception as error:  # openpyxl raises many kinds of errors for broken files
        raise HTTPException(422, UNREADABLE) from error


def _sheet_rows(sheet) -> Iterator[tuple[int, Any]]:
    try:
        yield from enumerate(sheet.iter_rows(values_only=True), start=1)
    except Exception as error:
        raise HTTPException(422, UNREADABLE) from error


def _xlsx_first_sheet(path: Path) -> Iterator[tuple[int, Any]]:
    with closing(_open_workbook(path)) as workbook:
        yield from _sheet_rows(workbook.worksheets[0])


def _count_xlsx_rows(path: Path) -> int:
    """All the rows of the workbook's sheets, counted in the file without reading a cell (an .xlsx
    is a zip of XML files with one <row> per row). Sheets of other things count too, so this can be
    too high, which only moves the progress bar until the check gives the real count."""
    try:
        with zipfile.ZipFile(path) as archive:
            sheets = [name for name in archive.namelist() if name.startswith("xl/worksheets/sheet")]
            return sum(_count_row_tags(archive, name) for name in sheets)
    except (zipfile.BadZipFile, OSError) as error:
        raise HTTPException(422, UNREADABLE) from error


def _count_row_tags(archive: zipfile.ZipFile, name: str) -> int:
    count, tail = 0, b""
    with archive.open(name) as sheet_file:
        while chunk := sheet_file.read(1024 * 1024):
            text = tail + chunk
            # A tag cut in two by the chunk's end is counted with the next chunk.
            cut = text.rfind(b"<")
            cut = cut if cut > len(text) - 16 else len(text)
            count += len(ROW_TAG.findall(text, 0, cut))
            tail = text[cut:]
    return count


def _skip_to_same_headers(rows: Iterator[tuple[int, Any]], headers: list[str]) -> bool:
    for _, row in islice(rows, 20):
        if not _row_is_empty(row):
            return _trimmed_texts(row) == headers
    return False


def _trimmed_texts(row: Any) -> list[str]:
    texts = [" ".join(str(value).split()) if not _is_empty(value) else "" for value in row]
    while texts and not texts[-1]:
        texts.pop()
    return texts


def _csv_rows(path: Path) -> Iterator[tuple[int, list[str]]]:
    # Excel in French saves CSV in Windows-1252 with ";" between columns; others use UTF-8 and ",".
    encoding = _csv_encoding(path)
    with open(path, encoding=encoding, newline="") as text_file:
        delimiter = _csv_delimiter(text_file.read(4096))
        text_file.seek(0)
        try:
            yield from enumerate(csv.reader(text_file, delimiter=delimiter), start=1)
        except csv.Error as error:  # e.g. a binary file, or a cell without its closing quote
            raise HTTPException(422, UNREADABLE) from error


def _csv_encoding(path: Path) -> str:
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        with open(path, "rb") as file:
            while chunk := file.read(1024 * 1024):
                decoder.decode(chunk)
            decoder.decode(b"", final=True)
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "cp1252"


def _csv_delimiter(top: str) -> str:
    try:
        return csv.Sniffer().sniff(top, delimiters=";,\t|").delimiter
    except csv.Error:
        return ";" if top.split("\n", 1)[0].count(";") > 0 else ","


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _row_is_empty(row: Any) -> bool:
    for value in row:
        if value is not None and (not isinstance(value, str) or value.strip()):
            return False
    return True


def _to_table(path: Path, file_name: str, numbered: list[tuple[int, list[Any]]], total: int) -> Table:
    if not numbered:
        raise HTTPException(422, "The file is empty.")

    # Files often start with a title line ("Inventaire au 15/10/2026"). The header is the first row
    # that is about as full as the fullest rows near the top.
    filled = [sum(not _is_empty(v) for v in row) for _, row in numbered[:20]]
    header_at = next(i for i, count in enumerate(filled) if count >= max(2, 0.6 * max(filled)) or count == max(filled))
    numbered = numbered[header_at:]
    header_number, header_row = numbered[0]
    width = max(len(row) for _, row in numbered)
    # Drop columns empty all the way down what we looked at (Excel often adds some at the end).
    used = [i for i in range(width) if any(i < len(row) and not _is_empty(row[i]) for _, row in numbered)]
    headers = [
        " ".join(str(header_row[i]).split()) if i < len(header_row) and not _is_empty(header_row[i])
        else f"Column {get_column_letter(i + 1)}"
        for i in used
    ]
    rows = [[row[i] if i < len(row) else None for i in used] for _, row in numbered[1:]]
    if not rows:
        raise HTTPException(422, "The file has a header row but no data under it.")
    return Table(
        path=path,
        file_name=file_name,
        headers=headers,
        first_rows=rows,
        row_count=len(rows) if len(numbered) + header_at < LOOK_AT_ROWS else total - header_at - 1,
        columns_in_use=used,
        header_cells=_trimmed_texts(header_row),
        header_row=header_number,
    )
