"""Builds the import test files in this folder. They are only for tests, never shown in the app.

Run inside the api container:  python tests/fixtures/make_fixtures.py

- parts_fr_messy.xlsx  French headers with accents and odd spacing, prices like "1 250,00 DH",
                       lowercase SKUs with spaces, empty rows, and 7 rows with problems.
- parts_en_clean.csv   English headers, comma separated, 12 new parts and 3 updates of French ones.
- sales_fr_messy.csv   ";" separated, Windows-1252 encoding (French Excel), dates 15/03/2026,
                       "45,00" prices, empty rows, and 4 rows with problems.
- sales_en_clean.xlsx  real Excel dates, weekly sales for 12 parts from April to October 2026.
"""

import csv
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook

HERE = Path(__file__).parent

# sku, name, brand, category, OEM reference, cost (MAD), price (MAD), minimum, quantity, branch, supplier
FRENCH_PARTS = [
    (" bp-001 ", "Plaquettes de frein avant", "Bosch", "Freinage", "0986494525", "180,00", "320,00", 10, 6, "Casablanca", "Auto Hall Pièces"),
    ("BP-002", "Plaquettes de frein arrière", "Bosch", "Freinage", "0986494526", "150", "275,50", 8, 14, "Casablanca", "Auto Hall Pièces"),
    ("DS-110", "Disque de frein avant (paire)", "Brembo", "Freinage", "09.A820.11", "420,00", "690,00", 4, 0, "Casablanca", "Brembo Maroc"),
    ("FL-200", "Filtre à huile", "Mann-Filter", "Filtration", "W 712/95", "35,50", "65,00", 20, 48, "Casablanca", "Distri Filtres"),
    ("FL-205", "Filtre à air moteur", "Mann-Filter", "Filtration", "C 2774/3", "60", "110,00", 15, 9, "Rabat", "Distri Filtres"),
    ("FL-207", "Filtre habitacle charbon actif", "Bosch", "Filtration", "1987432397", "75,00", "140,00", 10, 22, "Rabat", "Auto Hall Pièces"),
    ("SP-104", "Bougie d'allumage iridium", "NGK", "Allumage", "ILKAR7B11", "55,00", "95,00", 24, 0, "Casablanca", "NGK Distribution"),
    ("SP-105", "Bougie de préchauffage", "Bosch", "Allumage", "0250202132", "85", "150", 12, 30, "Casablanca", "Auto Hall Pièces"),
    ("BT-912", "Batterie 12V 70Ah", "Varta", "Électricité", "E13", "1 250,00 DH", "1 650,00 DH", 3, 5, "Casablanca", "Varta Maroc"),
    ("BT-913", "Batterie 12V 60Ah", "Varta", "Électricité", "D59", "1 050,00", "1 390,00", 3, 2, "Rabat", "Varta Maroc"),
    ("AM-300", "Amortisseur avant gauche", "Monroe", "Suspension", "G7414", "520,00", "840,00", 2, 4, "Casablanca", "Monroe Afrique"),
    ("AM-301", "Amortisseur avant droit", "Monroe", "Suspension", "G7415", "520,00", "840,00", 2, 3, "Casablanca", "Monroe Afrique"),
    ("CR-450", "Courroie de distribution (kit)", "Gates", "Moteur", "K015603XS", "690,00", "1 090,00", 2, 7, "Casablanca", "Gates Maghreb"),
    ("CR-451", "Courroie d'accessoires", "Gates", "Moteur", "6PK1070", "120", "210", 5, 11, "Rabat", "Gates Maghreb"),
    ("PE-600", "Pompe à eau", "SKF", "Refroidissement", "VKPC 85308", "380,00", "620,00", 2, 1, "Casablanca", "SKF Maroc"),
    ("TH-610", "Thermostat moteur", "Wahler", "Refroidissement", "4256.87D", "140,00", "245,00", 3, 6, "Casablanca", "Auto Hall Pièces"),
    ("RL-700", "Rotule de direction", "TRW", "Direction", "JTE1078", "95,00", "170,00", 6, 13, "Rabat", "TRW Distribution"),
    ("RL-701", "Biellette de barre stabilisatrice", "TRW", "Suspension", "JTS1033", "80", "150", 6, 0, "Rabat", "TRW Distribution"),
    ("EM-800", "Kit embrayage", "Valeo", "Transmission", "826317", "1 480,00", "2 190,00", 1, 2, "Casablanca", "Valeo Service"),
    ("HL-900", "Huile moteur 5W30 5L", "Total", "Lubrifiants", "QUARTZ 9000", "290,00", "420,00", 12, 35, "Casablanca", "Total Maroc"),
    ("HL-901", "Liquide de refroidissement 5L", "Total", "Lubrifiants", "COOLELF", "95", "160", 10, 18, "Casablanca", "Total Maroc"),
    ("EP-950", "Balai d'essuie-glace 600 mm", "Bosch", "Accessoires", "3397008536", "70,00", "125,00", 10, 26, "Casablanca", "Auto Hall Pièces"),
]

# Rows that must come back as problems in the Check step.
FRENCH_PROBLEM_ROWS = [
    ("", "Capteur ABS avant", "Bosch", "Électricité", "0265007896", "310,00", "520,00", 2, 3, "Casablanca", "Auto Hall Pièces"),  # SKU is missing
    ("LP-120", "Lampe H7 55W", "Philips", "Éclairage", "12972PR", "30,00", "55,00", 20, "douze", "Casablanca", "Philips Auto"),  # quantity not a number
    ("LP-121", "Lampe H4 60/55W", "Philips", "Éclairage", "12342PR", "28,00", "50,00", 20, "2,5", "Casablanca", "Philips Auto"),  # not whole
    ("FL-210", "Filtre à gasoil", "Mann-Filter", "Filtration", "WK 820/14", "85,00", "150,00", 8, 10, "Casablanca", "Distri Filtres"),  # twice
    ("FL-210", "Filtre à gasoil (doublon)", "Mann-Filter", "Filtration", "WK 820/14", "85,00", "150,00", 8, 12, "Rabat", "Distri Filtres"),  # twice
    ("RD-130", "Radiateur moteur", "Valeo", "Refroidissement", "735054", "900,00", "-45", 1, 1, "Casablanca", "Valeo Service"),  # negative price
    ("XX-999", "", "Bosch", "Divers", "", "10,00", "20,00", 0, 1, "Casablanca", ""),  # new part without name
]

FRENCH_HEADERS = [
    "  Réf. ", "Désignation", "Marque", "Famille", "Réf  OEM", "Prix d'achat (DH)", "Prix de vente",
    "Stock mini", "Qté en stock", "Dépôt", "Fournisseur",
]


def make_parts_fr_messy() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Articles"
    sheet.append(["Inventaire au 15/10/2026"])  # a title line above the table, like real files
    sheet.append([])
    sheet.append(FRENCH_HEADERS + [None])  # an empty extra column at the end
    for index, row in enumerate(FRENCH_PARTS):
        sheet.append(list(row))
        if index in (5, 14):
            sheet.append([None] * len(FRENCH_HEADERS))  # empty rows in the middle
    for row in FRENCH_PROBLEM_ROWS:
        sheet.append(list(row))
    workbook.save(HERE / "parts_fr_messy.xlsx")


ENGLISH_PARTS = [
    ("BK-310", "Brake caliper front left", "ATE", "Brakes", "24.3348-1712.5", "650.00", "990.00", "2", "3", "Main", "ATE Morocco"),
    ("BK-311", "Brake caliper front right", "ATE", "Brakes", "24.3348-1713.5", "650.00", "990.00", "2", "1", "Main", "ATE Morocco"),
    ("BK-320", "Brake fluid DOT4 1L", "Bosch", "Brakes", "1987479107", "55.00", "95.00", "10", "40", "Main", "Auto Hall Pieces"),
    ("WB-410", "Wheel bearing kit front", "SKF", "Suspension", "VKBA 3637", "310.00", "520.00", "3", "0", "Main", "SKF Morocco"),
    ("WB-411", "Wheel bearing kit rear", "SKF", "Suspension", "VKBA 3569", "290.00", "490.00", "3", "6", "Main", "SKF Morocco"),
    ("ST-500", "Starter motor", "Valeo", "Electrical", "438170", "1150.00", "1690.00", "1", "1", "Main", "Valeo Service"),
    ("AL-510", "Alternator 90A", "Valeo", "Electrical", "439561", "1350.00", "1990.00", "1", "0", "Main", "Valeo Service"),
    ("IC-520", "Ignition coil", "Bosch", "Ignition", "0221604115", "260.00", "420.00", "4", "9", "Main", "Auto Hall Pieces"),
    ("FP-530", "Fuel pump", "Bosch", "Fuel", "0580453453", "780.00", "1190.00", "1", "2", "Main", "Auto Hall Pieces"),
    ("EX-540", "Exhaust gasket", "Elring", "Exhaust", "263.920", "25.00", "45.00", "10", "37", "Main", "Elring Distribution"),
    ("TR-550", "Tie rod end", "Lemforder", "Steering", "37061 01", "140.00", "230.00", "4", "8", "Main", "ZF Aftermarket"),
    ("HS-560", "Radiator hose upper", "Gates", "Cooling", "05-3123", "75.00", "130.00", "5", "12", "Main", "Gates Maghreb"),
    # Updates of parts from the French file: new price, new minimum, new quantity.
    ("BP-001", "Front brake pads", "Bosch", "Freinage", "0986494525", "185.00", "330.00", "12", "6", "Casablanca", "Auto Hall Pièces"),
    ("FL-200", "Oil filter", "Mann-Filter", "Filtration", "W 712/95", "35.50", "65.00", "20", "52", "Casablanca", "Distri Filtres"),
    ("SP-104", "Spark plug iridium", "NGK", "Allumage", "ILKAR7B11", "55.00", "95.00", "24", "36", "Casablanca", "NGK Distribution"),
]

ENGLISH_HEADERS = [
    "SKU", "Name", "Brand", "Category", "OEM reference", "Unit cost", "Sale price",
    "Minimum stock", "Quantity", "Branch", "Supplier",
]


def make_parts_en_clean() -> None:
    with open(HERE / "parts_en_clean.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(ENGLISH_HEADERS)
        writer.writerows(ENGLISH_PARTS)


FRENCH_SALES = [
    ("03/10/2026", "BP-001", "2", "320,00", "Casablanca"),
    ("03/10/2026", "FL-200", "4", "65,00", "Casablanca"),
    ("04/10/2026", "HL-900", "3", "420,00", "Casablanca"),
    ("05/10/2026", "SP-104", "8", "95,00", "Casablanca"),
    ("06/10/2026", "FL-205", "1", "110,00", "Rabat"),
    ("07/10/2026", "BT-912", "1", "1 650,00", "Casablanca"),
    ("08/10/2026", "bp-002 ", "2", "275,50", "Casablanca"),
    ("09/10/2026", "EP-950", "2", "125", "Casablanca"),
    ("10/10/2026", "RL-700", "2", "170,00", "Rabat"),
    ("11/10/2026", "FL-200", "6", "65,00", "Casablanca"),
    ("12/10/2026", "HL-901", "2", "160,00", "Casablanca"),
    ("13/10/2026", "CR-451", "1", "210,00", "Rabat"),
    ("14/10/2026", "BP-001", "1", "320,00", "Casablanca"),
    ("14/10/2026", "SP-105", "4", "150,00", "Casablanca"),
    ("15/10/2026", "HL-900", "2", "420,00", "Casablanca"),
    ("15/10/2026", "FL-207", "1", "140,00", "Rabat"),
]

FRENCH_SALES_PROBLEMS = [
    ("31/02/2026", "BP-001", "1", "320,00", "Casablanca"),  # date is not valid
    ("12/10/2026", "ZZ-404", "1", "99,00", "Casablanca"),  # SKU not in parts
    ("13/10/2026", "FL-200", "0", "65,00", "Casablanca"),  # quantity 0
    ("13/10/2026", "FL-205", "deux", "110,00", "Rabat"),  # quantity not a number
]


def make_sales_fr_messy() -> None:
    lines = ["Date de vente;Réf. article;Qté;Prix unitaire (DH);Dépôt"]
    for index, row in enumerate(FRENCH_SALES):
        lines.append(";".join(row))
        if index == 7:
            lines.append(";;;;")  # an empty row
    lines += [";".join(row) for row in FRENCH_SALES_PROBLEMS]
    (HERE / "sales_fr_messy.csv").write_bytes(("\r\n".join(lines) + "\r\n").encode("cp1252"))


ENGLISH_SALES_SKUS = ["BP-001", "BP-002", "FL-200", "FL-205", "SP-104", "SP-105", "HL-900", "HL-901",
                      "EP-950", "AM-300", "CR-450", "TH-610"]


def make_sales_en_clean() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sales"
    sheet.append(["Date", "SKU", "Quantity", "Unit price", "Branch"])
    prices = {row[0].strip().upper(): row[6] for row in FRENCH_PARTS}
    first_monday = date(2026, 4, 6)
    for week in range(27):
        day = first_monday + timedelta(weeks=week)
        for index, sku in enumerate(ENGLISH_SALES_SKUS):
            # The last three parts stop selling in June: they become dead stock.
            if index >= 9 and day > date(2026, 6, 1):
                continue
            sheet.append([day, sku, (index % 4) + 1, float(prices[sku].replace(" ", "").replace("DH", "").replace(",", ".")), "Casablanca"])
    workbook.save(HERE / "sales_en_clean.xlsx")


if __name__ == "__main__":
    make_parts_fr_messy()
    make_parts_en_clean()
    make_sales_fr_messy()
    make_sales_en_clean()
    print("Fixture files written to", HERE)
