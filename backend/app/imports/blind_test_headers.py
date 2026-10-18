"""A second, independent set of labeled headers, written once, used only to report an honest
score — never to tune the keyword rule or retrain the model.

Unlike header_examples.py (used for training the scikit-learn model and for the keyword rule's
own development), nothing here was used to write or adjust any matching rule. It is written
before matching.py's keyword lists are touched for review feedback, and is not edited afterward
to make a score look better. Some headers here are deliberately awkward (abbreviations, a
synonym the keyword rule has never seen) — a lower score on those is an honest result, not a bug.
"""

from app.imports.header_examples import HeaderExample

PARTS_HEADER_SETS: list[list[HeaderExample]] = [
    # 1. Clean English, different wording than header_examples.py
    [
        ("Part Number", "sku"), ("Description", "name"), ("Make", "brand"), ("Product Type", "category"),
        ("Manufacturer Part Number", "oem_reference"), ("Buying Price", "unit_cost"), ("Selling Price", "sale_price"),
        ("Reorder Point", "min_stock"), ("Available Qty", "quantity"), ("Depot", "branch"), ("Vendor Name", "supplier"),
    ],
    # 2. Clean French, different wording
    [
        ("Code article", "sku"), ("Libellé", "name"), ("Marque", "brand"), ("Catégorie", "category"),
        ("Référence constructeur", "oem_reference"), ("Coût unitaire", "unit_cost"), ("Prix de vente TTC", "sale_price"),
        ("Seuil de réapprovisionnement", "min_stock"), ("Quantité disponible", "quantity"), ("Succursale", "branch"),
        ("Nom fournisseur", "supplier"),
    ],
    # 3. Clean Arabic, different wording
    [
        ("رقم الصنف", "sku"), ("وصف المنتج", "name"), ("العلامة", "brand"), ("نوع المنتج", "category"),
        ("الرقم الأصلي", "oem_reference"), ("تكلفة الشراء", "unit_cost"), ("ثمن البيع", "sale_price"),
        ("حد إعادة الطلب", "min_stock"), ("الكمية بالمخزون", "quantity"), ("الفرع", "branch"), ("اسم المورد", "supplier"),
    ],
    # 4. Very messy English abbreviations — a genuinely hard case, on purpose
    [
        ("P/N", "sku"), ("Desc.", "name"), ("Mfr.", "brand"), ("Grp", "category"), ("Mfr Ref", "oem_reference"),
        ("Buy $", "unit_cost"), ("Sell $", "sale_price"), ("Reorder Qty", "min_stock"), ("Avail", "quantity"),
        ("Whse", "branch"), ("Supp", "supplier"),
    ],
    # 5. Messy French, no accents
    [
        ("code produit", "sku"), ("nom produit", "name"), ("fabricant", "brand"), ("rayon", "category"),
        ("ref fabricant", "oem_reference"), ("cout dh", "unit_cost"), ("prix dh", "sale_price"),
        ("reappro mini", "min_stock"), ("en stock", "quantity"), ("entrepot", "branch"), ("four.", "supplier"),
    ],
    # 6. Mixed French/English, with "Rayon" (shelf/aisle) for category — a synonym not in the rule
    [
        ("Reference", "sku"), ("Libelle produit", "name"), ("Brand", "brand"), ("Rayon", "category"),
        ("OEM Ref", "oem_reference"), ("Prix Achat HT", "unit_cost"), ("Prix Vente TTC", "sale_price"),
        ("Stock Alerte", "min_stock"), ("Qte Disponible", "quantity"), ("Depot", "branch"), ("Fournisseur", "supplier"),
    ],
    # 7. Database export style
    [
        ("ITEM_REF", "sku"), ("ITEM_DESC", "name"), ("MFR_NAME", "brand"), ("PRODUCT_CAT", "category"),
        ("OEM_NUMBER", "oem_reference"), ("COST_PRICE", "unit_cost"), ("SALE_PRICE", "sale_price"),
        ("REORDER_LEVEL", "min_stock"), ("QTY_AVAILABLE", "quantity"), ("WAREHOUSE_CODE", "branch"),
        ("VENDOR_CODE", "supplier"),
    ],
    # 8. Arabic with an English word tacked on, messier than the bilingual-parenthetical style
    [
        ("رقم القطعة Ref", "sku"), ("اسم القطعة Name", "name"), ("الماركة Brand", "brand"), ("نوع القطعة Cat", "category"),
        ("OEM رقم", "oem_reference"), ("تكلفة DH", "unit_cost"), ("سعر DH", "sale_price"), ("حد ادنى", "min_stock"),
        ("متوفر الكمية", "quantity"), ("مكان التخزين", "branch"), ("مورد القطعة", "supplier"),
    ],
    # 9. Bilingual parenthetical, different words than header_examples.py's version
    [
        ("القطعة (SKU)", "sku"), ("التسمية (Name)", "name"), ("العلامة (Brand)", "brand"), ("الصنف (Category)", "category"),
        ("مرجع (OEM)", "oem_reference"), ("الكلفة (Cost)", "unit_cost"), ("السعر (Price)", "sale_price"),
        ("أدنى حد (Min)", "min_stock"), ("متوفر (Qty)", "quantity"), ("الموقع (Branch)", "branch"),
        ("المزود (Supplier)", "supplier"),
    ],
    # 10. Clean file with two columns that aren't any of our fields
    [
        ("SKU", "sku"), ("Name", "name"), ("Brand", "brand"), ("Category", "category"), ("OEM Reference", "oem_reference"),
        ("Unit Cost", "unit_cost"), ("Sale Price", "sale_price"), ("Min Stock", "min_stock"), ("Quantity", "quantity"),
        ("Branch", "branch"), ("Supplier", "supplier"), ("Last Updated By", None), ("Row ID", None),
    ],
    # 11. Extremely abbreviated French, different abbreviations than header_examples.py's version
    [
        ("no", "sku"), ("libel", "name"), ("mq", "brand"), ("typ", "category"), ("oem", "oem_reference"),
        ("cu", "unit_cost"), ("pv", "sale_price"), ("seuil", "min_stock"), ("dispo", "quantity"), ("succ", "branch"),
        ("frs", "supplier"),
    ],
]

SALES_HEADER_SETS: list[list[HeaderExample]] = [
    # 1. Clean English, different wording
    [("Sold On", "date"), ("Part Number", "sku"), ("Units", "quantity"), ("Price Each", "unit_price"), ("Store", "branch")],
    # 2. Clean French, different wording
    [
        ("Date d'achat", "date"), ("Code article", "sku"), ("Quantité vendue", "quantity"), ("Prix TTC", "unit_price"),
        ("Succursale", "branch"),
    ],
    # 3. Clean Arabic, different wording
    [("تاريخ العملية", "date"), ("رقم الصنف", "sku"), ("الكمية المباعة", "quantity"), ("السعر الفردي", "unit_price"), ("الفرع", "branch")],
    # 4. Very messy English abbreviations
    [("D8", "date"), ("P/N", "sku"), ("Qty", "quantity"), ("Each", "unit_price"), ("Loc.", "branch")],
    # 5. Messy French, no accents
    [("date op", "date"), ("ref", "sku"), ("qte", "quantity"), ("pu dh", "unit_price"), ("depot", "branch")],
    # 6. Mixed French/English
    [("Sale Date", "date"), ("Reference", "sku"), ("Qty Sold", "quantity"), ("Prix Unitaire", "unit_price"), ("Branch", "branch")],
    # 7. Database export style
    [("TXN_DATE", "date"), ("ITEM_REF", "sku"), ("UNITS_SOLD", "quantity"), ("PRICE_EACH", "unit_price"), ("STORE_CODE", "branch")],
    # 8. Arabic with an English word tacked on
    [
        ("تاريخ البيع DATE", "date"), ("رقم القطعة REF", "sku"), ("الكمية QTY", "quantity"), ("سعر الوحدة DH PRICE", "unit_price"),
        ("الفرع BRANCH", "branch"),
    ],
    # 9. File with two columns that aren't any of our fields
    [
        ("Date", "date"), ("SKU", "sku"), ("Quantity", "quantity"), ("Unit price", "unit_price"), ("Branch", "branch"),
        ("Cashier", None), ("Receipt No", None),
    ],
]
