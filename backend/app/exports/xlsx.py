"""Writes an .xlsx file row by row, straight into the zip file: the data export of a big shop
(20 million sales lines) in a few minutes instead of an hour.

An .xlsx file is a zip of XML files (the Office Open XML standard, ECMA-376). This writes only
what the export needs: text, whole and decimal numbers, yes/no, dates, date-times and a bold
header row. Each different text is stored once (the "shared strings"), so a part number sold
10,000 times takes the room of one.
"""

import re
import zipfile
from datetime import date, datetime
from typing import IO, Any
from xml.sax.saxutils import escape

MAX_ROWS = 1_048_576  # Excel can't open a sheet with more rows than this
EXCEL_DAY_ZERO = date(1899, 12, 30)  # Excel counts days from here
EXCEL_TIME_ZERO = datetime(1899, 12, 30)
NOT_IN_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")  # characters XML can't hold

DATE_STYLE, DATE_TIME_STYLE, BOLD_STYLE = 1, 2, 3  # positions in STYLES' cellXfs
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELATIONSHIPS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_START = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
STYLES = f"""{XML_START}<styleSheet xmlns="{MAIN}">
<numFmts count="2"><numFmt numFmtId="164" formatCode="yyyy-mm-dd"/><numFmt numFmtId="165" formatCode="yyyy-mm-dd hh:mm:ss"/></numFmts>
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""
ROWS_PER_WRITE = 5000
COLUMN_WIDTH = 20  # characters: wide enough for a date and time, so Excel shows it instead of ####


class Sheet:
    def __init__(self, book: "Workbook", name: str, number: int):
        self.book = book
        self.name = name  # can still change until the workbook is closed
        self.number = number
        self.row_count = 0
        self._file = book.zip.open(f"xl/worksheets/sheet{number}.xml", "w", force_zip64=True)
        self._file.write(f'{XML_START}<worksheet xmlns="{MAIN}"><sheetFormatPr defaultColWidth="{COLUMN_WIDTH}" defaultRowHeight="15"/><sheetData>'.encode())
        self._waiting: list[bytes] = []

    def header(self, texts: list[str]) -> None:
        """The first row, in bold."""
        self.row_count += 1
        cells = "".join(
            f'<c r="{_column(index)}1" s="{BOLD_STYLE}" t="s"><v>{self.book.text_number(text)}</v></c>'
            for index, text in enumerate(texts)
        )
        self._waiting.append(f'<row r="1">{cells}</row>'.encode())

    def append(self, values: list[Any]) -> None:
        """One row. None leaves the cell empty."""
        row = self.row_count + 1
        text_number = self.book.text_number
        cells = [f'<row r="{row}">']
        for column, value in zip(COLUMNS, values):
            kind = type(value)
            if kind is str:
                cells.append(f'<c r="{column}{row}" t="s"><v>{text_number(value)}</v></c>')
            elif kind is int or kind is float:
                cells.append(f'<c r="{column}{row}"><v>{value!r}</v></c>')
            elif kind is date:
                cells.append(f'<c r="{column}{row}" s="{DATE_STYLE}"><v>{(value - EXCEL_DAY_ZERO).days}</v></c>')
            elif kind is datetime:
                days = (value - EXCEL_TIME_ZERO).total_seconds() / 86400
                cells.append(f'<c r="{column}{row}" s="{DATE_TIME_STYLE}"><v>{days!r}</v></c>')
            elif kind is bool:
                cells.append(f'<c r="{column}{row}" t="b"><v>{int(value)}</v></c>')
            elif value is not None:
                raise TypeError(f"Can't write {kind.__name__} into an Excel cell")
        cells.append("</row>")
        self.append_xml("".join(cells).encode())

    def append_xml(self, row: bytes) -> None:
        """One row already written as XML (a <row> element), for rows PostgreSQL builds itself."""
        self.row_count += 1
        self._waiting.append(row)
        if len(self._waiting) >= ROWS_PER_WRITE:
            self._write_waiting()

    def close(self) -> None:
        self._write_waiting()
        self._file.write(b"</sheetData></worksheet>")
        self._file.close()

    def _write_waiting(self) -> None:
        self._file.write(b"".join(self._waiting))
        self._waiting.clear()


class Workbook:
    """Sheets are written one after the other; `first=True` puts a sheet first in Excel's tab order
    even when it is written last (a "Read me" that counts the other sheets' rows)."""

    def __init__(self, file: IO[bytes]):
        # Fastest compression level: the file is a little bigger, made several times faster.
        self.zip = zipfile.ZipFile(file, "w", zipfile.ZIP_DEFLATED, compresslevel=1)
        self.sheets: list[Sheet] = []
        self._open: Sheet | None = None
        self._texts: list[str] = []
        self._text_numbers: dict[str, int] = {}

    def add_sheet(self, name: str, first: bool = False) -> Sheet:
        if self._open:
            self._open.close()
        self._open = Sheet(self, name, len(self.sheets) + 1)
        self.sheets.insert(0 if first else len(self.sheets), self._open)
        return self._open

    def text_number(self, text: str) -> int:
        """Where `text` is in the shared texts (added the first time it's seen)."""
        number = self._text_numbers.get(text)
        if number is None:
            number = self._text_numbers[text] = len(self._texts)
            self._texts.append(text)
        return number

    def add_texts(self, texts: list[str]) -> int:
        """Adds `texts` one after the other and says where the first one is, so rows built
        elsewhere (by PostgreSQL) can point at text number first + position."""
        first = len(self._texts)
        self._texts += texts
        for number, text in enumerate(texts, start=first):
            self._text_numbers.setdefault(text, number)
        return first

    def close(self) -> None:
        if self._open:
            self._open.close()
        self._write_texts()
        sheets = "".join(
            f'<sheet name="{escape(sheet.name, {chr(34): "&quot;"})}" sheetId="{sheet.number}" r:id="rId{sheet.number}"/>'
            for sheet in self.sheets
        )
        self.zip.writestr("xl/workbook.xml", f'{XML_START}<workbook xmlns="{MAIN}" xmlns:r="{RELATIONSHIPS}"><sheets>{sheets}</sheets></workbook>')
        links = "".join(
            f'<Relationship Id="rId{sheet.number}" Type="{RELATIONSHIPS}/worksheet" Target="worksheets/sheet{sheet.number}.xml"/>'
            for sheet in self.sheets
        )
        links += f'<Relationship Id="rIdStyles" Type="{RELATIONSHIPS}/styles" Target="styles.xml"/>'
        links += f'<Relationship Id="rIdTexts" Type="{RELATIONSHIPS}/sharedStrings" Target="sharedStrings.xml"/>'
        self.zip.writestr("xl/_rels/workbook.xml.rels", f'{XML_START}<Relationships xmlns="{PACKAGE_RELATIONSHIPS}">{links}</Relationships>')
        self.zip.writestr("xl/styles.xml", STYLES)
        self.zip.writestr("_rels/.rels", f'{XML_START}<Relationships xmlns="{PACKAGE_RELATIONSHIPS}">'
                          f'<Relationship Id="rId1" Type="{RELATIONSHIPS}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        self.zip.writestr("[Content_Types].xml", self._content_types())
        self.zip.close()

    def _write_texts(self) -> None:
        with self.zip.open("xl/sharedStrings.xml", "w", force_zip64=True) as file:
            file.write(f'{XML_START}<sst xmlns="{MAIN}" uniqueCount="{len(self._texts)}">'.encode())
            for text in self._texts:
                file.write(f'<si><t xml:space="preserve">{escape(NOT_IN_XML.sub("", text))}</t></si>'.encode())
            file.write(b"</sst>")

    def _content_types(self) -> str:
        office = "application/vnd.openxmlformats-officedocument.spreadsheetml"
        parts = "".join(
            f'<Override PartName="/xl/worksheets/sheet{sheet.number}.xml" ContentType="{office}.worksheet+xml"/>'
            for sheet in self.sheets
        )
        return (
            f'{XML_START}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/xl/workbook.xml" ContentType="{office}.sheet.main+xml"/>'
            f'<Override PartName="/xl/styles.xml" ContentType="{office}.styles+xml"/>'
            f'<Override PartName="/xl/sharedStrings.xml" ContentType="{office}.sharedStrings+xml"/>'
            f"{parts}</Types>"
        )


def _column(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


COLUMNS = [_column(index) for index in range(16_384)]  # A to XFD, every column Excel has
