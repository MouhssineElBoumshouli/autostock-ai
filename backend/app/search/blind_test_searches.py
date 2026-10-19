"""Labeled searches used only to report an honest score for part search — never to tune it.

Written before any search code. Not edited afterward to make a score look better.

The shop: the test fixture files imported in order, parts_fr_messy.xlsx then parts_en_clean.csv
(34 parts; the English file renames BP-001, FL-200 and SP-104 to English names).

Each line: (what the counter employee types, the part numbers that count as the right answer).
Two part numbers are given only when both are equally right (left/right pair, two batteries).
Some searches are deliberately hard (Darija, Arabic for a part named only in English) — a miss
on those is an honest result, not a bug.
"""

BlindSearch = tuple[str, tuple[str, ...]]

BLIND_SEARCHES: list[BlindSearch] = [
    # Typos
    ("plaquete frein arriere", ("BP-002",)),
    ("amortiseur avant droit", ("AM-301",)),
    ("courroi distribution", ("CR-450",)),
    ("batery 70ah", ("BT-912",)),
    ("altenator", ("AL-510",)),
    ("termostat", ("TH-610",)),
    ("embrayag", ("EM-800",)),
    ("stater motor", ("ST-500",)),
    ("bougie prechaufage", ("SP-105",)),
    ("essuie glasse", ("EP-950",)),
    ("radiater hose", ("HS-560",)),
    ("biellete stabilisatrice", ("RL-701",)),
    # Codes typed differently (spaces, dashes, dots, case, partial)
    ("0 986 494 525", ("BP-001",)),
    ("bp001", ("BP-001",)),
    ("BP 002", ("BP-002",)),
    ("w71295", ("FL-200",)),
    ("W-712-95", ("FL-200",)),
    ("c2774/3", ("FL-205",)),
    ("vkba3637", ("WB-410",)),
    ("09a82011", ("DS-110",)),
    ("24.3348.1713.5", ("BK-311",)),
    ("6pk 1070", ("CR-451",)),
    ("ilkar7b11", ("SP-104",)),
    ("jte 1078", ("RL-700",)),
    ("tr550", ("TR-550",)),
    ("3706101", ("TR-550",)),
    ("0580 453 453", ("FP-530",)),
    ("k015603", ("CR-450",)),
    ("4256.87", ("TH-610",)),
    ("vkpc85308", ("PE-600",)),
    # French
    ("filtre a huile", ("FL-200",)),
    ("étrier de frein avant droit", ("BK-311",)),
    ("liquide de frein", ("BK-320",)),
    ("pompe à essence", ("FP-530",)),
    ("roulement de roue avant", ("WB-410",)),
    ("démarreur", ("ST-500",)),
    ("bobine d'allumage", ("IC-520",)),
    ("joint d'échappement", ("EX-540",)),
    ("durite radiateur", ("HS-560",)),
    ("bougie d'allumage", ("SP-104",)),
    # English
    ("rear brake pads", ("BP-002",)),
    ("water pump", ("PE-600",)),
    ("timing belt kit", ("CR-450",)),
    ("clutch kit", ("EM-800",)),
    ("cabin filter", ("FL-207",)),
    ("air filter", ("FL-205",)),
    ("front shock absorber left", ("AM-300",)),
    ("coolant", ("HL-901",)),
    ("engine oil 5w30", ("HL-900",)),
    ("wiper blade", ("EP-950",)),
    # Arabic
    ("فلتر الزيت", ("FL-200",)),
    ("مضخه الماء", ("PE-600",)),
    ("بطارية 60", ("BT-913",)),
    ("شمعة الإشعال", ("SP-104",)),
    ("فحمات الفرامل الخلفية", ("BP-002",)),
    ("زيت المحرك", ("HL-900",)),
    ("مضخة الوقود", ("FP-530",)),
    ("فِلْتَر الهواء", ("FL-205",)),
    ("مساعد", ("AM-300", "AM-301")),
    # Darija
    ("بوجي", ("SP-104",)),
    ("لامبرياج", ("EM-800",)),
    ("الباطري", ("BT-912", "BT-913")),
    ("ديمارور", ("ST-500",)),
    ("ديسك فران", ("DS-110",)),
    # Partial words
    ("amort", ("AM-300", "AM-301")),
    ("therm", ("TH-610",)),
    ("alter", ("AL-510",)),
    ("radia hose", ("HS-560",)),
    ("stab", ("RL-701",)),
]
