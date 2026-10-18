"""Real-looking column headers, each labeled with the field it means (or None to ignore).

Used to measure the keyword rule and the scikit-learn model in matching.py, so we can be honest
about how well each one works instead of guessing. Mixes French, English, Arabic, abbreviations
and messy spelling, the way real shops actually write their spreadsheets.

Each "set" is one imaginary file's header row. Splitting by whole sets (not by single header)
for training/testing means the test measures something real: how well a matcher does on a file
shaped unlike anything it has seen, not just a header it has memorized.
"""

HeaderExample = tuple[str, str | None]  # (header text, field key, or None to ignore)

PARTS_HEADER_SETS: list[list[HeaderExample]] = [
    # 1. Clean English
    [
        ("SKU", "sku"), ("Name", "name"), ("Brand", "brand"), ("Category", "category"),
        ("OEM reference", "oem_reference"), ("Unit cost", "unit_cost"), ("Sale price", "sale_price"),
        ("Minimum stock", "min_stock"), ("Quantity", "quantity"), ("Branch", "branch"), ("Supplier", "supplier"),
    ],
    # 2. Clean French
    [
        ("Réf.", "sku"), ("Désignation", "name"), ("Marque", "brand"), ("Famille", "category"),
        ("Réf OEM", "oem_reference"), ("Prix d'achat", "unit_cost"), ("Prix de vente", "sale_price"),
        ("Stock mini", "min_stock"), ("Qté en stock", "quantity"), ("Dépôt", "branch"), ("Fournisseur", "supplier"),
    ],
    # 3. Clean Arabic
    [
        ("رمز القطعة", "sku"), ("الاسم", "name"), ("الماركة", "brand"), ("الفئة", "category"),
        ("المرجع الأصلي", "oem_reference"), ("سعر الشراء", "unit_cost"), ("سعر البيع", "sale_price"),
        ("الحد الأدنى للمخزون", "min_stock"), ("الكمية", "quantity"), ("الفرع", "branch"), ("المورد", "supplier"),
    ],
    # 4. Messy English: abbreviations, caps
    [
        ("Part No", "sku"), ("DESC", "name"), ("Mfr", "brand"), ("Cat", "category"), ("OEM#", "oem_reference"),
        ("Cost Price", "unit_cost"), ("Sell Price", "sale_price"), ("Min Qty", "min_stock"),
        ("On Hand", "quantity"), ("Loc", "branch"), ("Vendor", "supplier"),
    ],
    # 5. Messy French: no accents, lowercase, abbreviations
    [
        ("ref", "sku"), ("designation", "name"), ("marque", "brand"), ("categorie", "category"),
        ("ref oem", "oem_reference"), ("prix achat dh", "unit_cost"), ("prix vente dh", "sale_price"),
        ("stock min", "min_stock"), ("qte stock", "quantity"), ("depot", "branch"), ("fournisseur", "supplier"),
    ],
    # 6. Mixed French/English, as a Moroccan shop might type it
    [
        ("Code", "sku"), ("Nom article", "name"), ("Brand", "brand"), ("Famille", "category"), ("OEM", "oem_reference"),
        ("Prix Achat (MAD)", "unit_cost"), ("Prix Vente (MAD)", "sale_price"), ("Stock Minimum", "min_stock"),
        ("Quantité", "quantity"), ("Branch", "branch"), ("Supplier", "supplier"),
    ],
    # 7. Excel export style: extra spacing and punctuation
    [
        (" SKU ", "sku"), (" Item Name ", "name"), (" Brand ", "brand"), (" Category ", "category"),
        (" OEM Ref. ", "oem_reference"), (" Cost (DH) ", "unit_cost"), (" Price (DH) ", "sale_price"),
        (" Min. Stock ", "min_stock"), (" Qty ", "quantity"), (" Warehouse ", "branch"), (" Supplier Name ", "supplier"),
    ],
    # 8. Arabic with Latin currency code mixed in
    [
        ("كود المنتج", "sku"), ("تسمية", "name"), ("الماركة", "brand"), ("نوع", "category"),
        ("رقم OEM", "oem_reference"), ("سعر الشراء DH", "unit_cost"), ("سعر البيع DH", "sale_price"),
        ("الحد الادنى", "min_stock"), ("الكمية المتوفرة", "quantity"), ("المستودع", "branch"), ("المورد", "supplier"),
    ],
    # 9. Alternate English wording
    [
        ("Item code", "sku"), ("Product name", "name"), ("Manufacturer", "brand"), ("Product category", "category"),
        ("Manufacturer reference", "oem_reference"), ("Purchase price", "unit_cost"), ("Retail price", "sale_price"),
        ("Reorder level", "min_stock"), ("Stock on hand", "quantity"), ("Store", "branch"), ("Vendor name", "supplier"),
    ],
    # 10. French with heavy abbreviation (accounting style)
    [
        ("N° réf", "sku"), ("Désign. article", "name"), ("Marque", "brand"), ("Sous-famille", "category"),
        ("Réf. constructeur", "oem_reference"), ("PA HT", "unit_cost"), ("PV TTC", "sale_price"),
        ("Seuil mini", "min_stock"), ("Stock dispo", "quantity"), ("Site", "branch"), ("Fournisseur", "supplier"),
    ],
    # 11. Database export style: caps and underscores
    [
        ("SKU_CODE", "sku"), ("PART_NAME", "name"), ("BRAND_NAME", "brand"), ("CATEGORY", "category"),
        ("OEM_REF", "oem_reference"), ("UNIT_COST", "unit_cost"), ("UNIT_PRICE", "sale_price"),
        ("MIN_STOCK", "min_stock"), ("QTY_ON_HAND", "quantity"), ("BRANCH_NAME", "branch"), ("SUPPLIER_NAME", "supplier"),
    ],
    # 12. Clean Arabic, different phrasing
    [
        ("رمز", "sku"), ("الوصف", "name"), ("العلامة التجارية", "brand"), ("التصنيف", "category"),
        ("مرجع الصانع", "oem_reference"), ("تكلفة الوحدة", "unit_cost"), ("سعر الوحدة", "sale_price"),
        ("أدنى كمية", "min_stock"), ("الكمية الحالية", "quantity"), ("الفرع", "branch"), ("المزود", "supplier"),
    ],
    # 13. French file with two columns that aren't any of our fields
    [
        ("Réf.", "sku"), ("Désignation", "name"), ("Marque", "brand"), ("Famille", "category"),
        ("Réf OEM", "oem_reference"), ("Prix Achat", "unit_cost"), ("Prix Vente", "sale_price"),
        ("Stock Mini", "min_stock"), ("Qté", "quantity"), ("Dépôt", "branch"), ("Fournisseur", "supplier"),
        ("Image", None), ("Remarques", None),
    ],
    # 14. English file with two columns that aren't any of our fields
    [
        ("SKU", "sku"), ("Name", "name"), ("Brand", "brand"), ("Category", "category"),
        ("OEM Reference", "oem_reference"), ("Cost", "unit_cost"), ("Price", "sale_price"),
        ("Min Stock", "min_stock"), ("Quantity", "quantity"), ("Branch", "branch"), ("Supplier", "supplier"),
        ("Internal ID", None), ("Notes", None),
    ],
    # 15. Very abbreviated French (the toughest case on purpose)
    [
        ("ref", "sku"), ("nom", "name"), ("mq", "brand"), ("cat", "category"), ("oem", "oem_reference"),
        ("pa", "unit_cost"), ("pv", "sale_price"), ("mini", "min_stock"), ("qte", "quantity"),
        ("dep", "branch"), ("four", "supplier"),
    ],
    # 16. Bilingual Arabic/English, as a two-language invoice template often looks
    [
        ("الكود (SKU)", "sku"), ("الاسم (Name)", "name"), ("الماركة (Brand)", "brand"), ("الفئة (Category)", "category"),
        ("مرجع OEM", "oem_reference"), ("سعر الشراء (Cost)", "unit_cost"), ("سعر البيع (Price)", "sale_price"),
        ("الحد الأدنى (Min)", "min_stock"), ("الكمية (Qty)", "quantity"), ("الفرع (Branch)", "branch"),
        ("المورد (Supplier)", "supplier"),
    ],
]

SALES_HEADER_SETS: list[list[HeaderExample]] = [
    # 1. Clean English
    [("Date", "date"), ("SKU", "sku"), ("Quantity", "quantity"), ("Unit price", "unit_price"), ("Branch", "branch")],
    # 2. Clean French
    [("Date", "date"), ("Réf.", "sku"), ("Qté", "quantity"), ("Prix unitaire", "unit_price"), ("Dépôt", "branch")],
    # 3. Clean Arabic
    [
        ("التاريخ", "date"), ("رمز القطعة", "sku"), ("الكمية", "quantity"), ("سعر الوحدة", "unit_price"),
        ("الفرع", "branch"),
    ],
    # 4. Messy English abbreviations
    [("Dt", "date"), ("Part No", "sku"), ("Qty", "quantity"), ("Price", "unit_price"), ("Loc", "branch")],
    # 5. Messy French, no accents
    [
        ("date vente", "date"), ("ref", "sku"), ("qte vendue", "quantity"), ("prix unit dh", "unit_price"),
        ("depot", "branch"),
    ],
    # 6. Mixed French/English
    [("Date de vente", "date"), ("SKU", "sku"), ("Quantity", "quantity"), ("Prix (DH)", "unit_price"), ("Branch", "branch")],
    # 7. Excel export spacing
    [
        (" Sale Date ", "date"), (" Item Code ", "sku"), (" Qty Sold ", "quantity"), (" Unit Price (DH) ", "unit_price"),
        (" Store ", "branch"),
    ],
    # 8. Arabic, messy mixed with currency code
    [
        ("تاريخ البيع", "date"), ("كود المنتج", "sku"), ("الكمية المباعة", "quantity"), ("سعر الوحدة DH", "unit_price"),
        ("المستودع", "branch"),
    ],
    # 9. Alternate English wording
    [
        ("Transaction date", "date"), ("Product code", "sku"), ("Units sold", "quantity"),
        ("Price per unit", "unit_price"), ("Location", "branch"),
    ],
    # 10. French, accounting abbreviations
    [("Date vte", "date"), ("N° réf", "sku"), ("Qté vendue", "quantity"), ("PU TTC", "unit_price"), ("Site", "branch")],
    # 11. Database export style
    [
        ("SALE_DATE", "date"), ("SKU_CODE", "sku"), ("QTY_SOLD", "quantity"), ("UNIT_PRICE", "unit_price"),
        ("BRANCH_NAME", "branch"),
    ],
    # 12. Clean Arabic, different phrasing
    [
        ("يوم البيع", "date"), ("المرجع", "sku"), ("عدد القطع المباعة", "quantity"), ("ثمن الوحدة", "unit_price"),
        ("الفرع", "branch"),
    ],
    # 13. File with two columns that aren't any of our fields
    [
        ("Date", "date"), ("SKU", "sku"), ("Quantity", "quantity"), ("Unit price", "unit_price"), ("Branch", "branch"),
        ("Customer", None), ("Invoice number", None),
    ],
    # 14. Bilingual Arabic/English
    [
        ("التاريخ (Date)", "date"), ("الكود (SKU)", "sku"), ("الكمية (Qty)", "quantity"), ("السعر (Price)", "unit_price"),
        ("الفرع (Branch)", "branch"),
    ],
]
