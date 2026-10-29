"""Words for the data export, in the owner's own language. Written by the server (the exported
file has no browser to translate it), the same exception app/ask/sentences/ already uses.

Only the "parts" and "sales" sheets need headers our own import screen can recognise by itself
(app/imports/fields.py: FIELD_LABELS); the sheets below are read-only, so their headers only need
to be plain words in the right language.
"""

from typing import TypedDict


class SheetLabels(TypedDict):
    read_me: str
    parts: str
    sales: str
    purchase_orders: str
    suppliers: str
    branches: str
    equivalent_parts: str
    users: str
    activity_log: str


SHEET_NAMES: dict[str, SheetLabels] = {
    "en": {
        "read_me": "Read me", "parts": "Parts", "sales": "Sales", "purchase_orders": "Purchase orders",
        "suppliers": "Suppliers", "branches": "Branches", "equivalent_parts": "Equivalent parts",
        "users": "Users", "activity_log": "Activity log",
    },
    "fr": {
        "read_me": "Lisez-moi", "parts": "Pièces", "sales": "Ventes", "purchase_orders": "Commandes fournisseurs",
        "suppliers": "Fournisseurs", "branches": "Succursales", "equivalent_parts": "Pièces équivalentes",
        "users": "Utilisateurs", "activity_log": "Journal d’activité",
    },
    "ar": {
        "read_me": "اقرأني", "parts": "القطع", "sales": "المبيعات", "purchase_orders": "أوامر الشراء",
        "suppliers": "الموردون", "branches": "الفروع", "equivalent_parts": "القطع المعادلة",
        "users": "المستخدمون", "activity_log": "سجل النشاط",
    },
}

# Read me sheet: shop name / export date / row counts.
READ_ME: dict[str, dict[str, str]] = {
    "en": {
        "title": "AutoStock AI -- all of your shop's data",
        "shop_name": "Shop", "export_date": "Exported on", "row_counts": "How many rows each sheet has",
    },
    "fr": {
        "title": "AutoStock AI -- toutes les données de votre magasin",
        "shop_name": "Magasin", "export_date": "Exporté le", "row_counts": "Nombre de lignes de chaque feuille",
    },
    "ar": {
        "title": "AutoStock AI -- جميع بيانات متجرك",
        "shop_name": "المتجر", "export_date": "تاريخ التصدير", "row_counts": "عدد صفوف كل ورقة",
    },
}

# "Stock - <branch name>" columns added to the Parts sheet, one per branch, so the file shows the
# full picture even though the import screen only reads the single, recognised "Quantity" column
# (the part's total) back in.
STOCK_AT: dict[str, str] = {"en": "Stock at", "fr": "Stock à", "ar": "المخزون في"}

PURCHASE_ORDER_HEADERS: dict[str, list[str]] = {
    "en": [
        "Order number", "Supplier", "Status", "Sent on", "Received on", "Part SKU", "Part name", "Branch",
        "Quantity", "Received quantity", "Unit cost",
    ],
    "fr": [
        "N° de commande", "Fournisseur", "Statut", "Envoyée le", "Reçue le", "Référence pièce", "Désignation",
        "Succursale", "Quantité", "Quantité reçue", "Coût unitaire",
    ],
    "ar": [
        "رقم الطلب", "المورد", "الحالة", "تاريخ الإرسال", "تاريخ الاستلام", "مرجع القطعة", "اسم القطعة",
        "الفرع", "الكمية", "الكمية المستلمة", "سعر الوحدة",
    ],
}

PURCHASE_ORDER_STATUS: dict[str, dict[str, str]] = {
    "en": {"draft": "Draft", "sent": "Sent", "received": "Received"},
    "fr": {"draft": "Brouillon", "sent": "Envoyée", "received": "Reçue"},
    "ar": {"draft": "مسودة", "sent": "مرسلة", "received": "مستلمة"},
}

SUPPLIER_HEADERS: dict[str, list[str]] = {
    "en": ["Name", "Phone", "Email", "Delivery time (days)"],
    "fr": ["Nom", "Téléphone", "E-mail", "Délai de livraison (jours)"],
    "ar": ["الاسم", "الهاتف", "البريد الإلكتروني", "مدة التوصيل (أيام)"],
}

BRANCH_HEADERS: dict[str, list[str]] = {
    "en": ["Name"], "fr": ["Nom"], "ar": ["الاسم"],
}

EQUIVALENT_HEADERS: dict[str, list[str]] = {
    "en": ["Part SKU", "Part name", "Equivalent SKU", "Equivalent name", "Source", "Linked by", "Linked on"],
    "fr": ["Référence pièce", "Désignation", "Référence équivalente", "Désignation équivalente", "Origine", "Lié par", "Lié le"],
    "ar": ["مرجع القطعة", "اسم القطعة", "المرجع المعادل", "الاسم المعادل", "المصدر", "ربطها", "تاريخ الربط"],
}

EQUIVALENT_SOURCE: dict[str, dict[str, str]] = {
    "en": {"manual": "Linked by a manager", "supplier_file": "Supplier's file"},
    "fr": {"manual": "Lié par un gérant", "supplier_file": "Fichier fournisseur"},
    "ar": {"manual": "ربطها مدير", "supplier_file": "ملف المورد"},
}

USER_HEADERS: dict[str, list[str]] = {
    "en": ["Name", "Email", "Role", "Active", "Last login"],
    "fr": ["Nom", "E-mail", "Rôle", "Actif", "Dernière connexion"],
    "ar": ["الاسم", "البريد الإلكتروني", "الدور", "نشط", "آخر تسجيل دخول"],
}

ROLE_NAMES: dict[str, dict[str, str]] = {
    "en": {"owner": "Owner", "manager": "Manager", "staff": "Staff"},
    "fr": {"owner": "Propriétaire", "manager": "Gérant", "staff": "Employé"},
    "ar": {"owner": "المالك", "manager": "مدير", "staff": "موظف"},
}

YES_NO: dict[str, dict[bool, str]] = {
    "en": {True: "Yes", False: "No"}, "fr": {True: "Oui", False: "Non"}, "ar": {True: "نعم", False: "لا"},
}

ACTIVITY_HEADERS: dict[str, list[str]] = {
    "en": ["Date", "Person", "Action", "What changed"],
    "fr": ["Date", "Personne", "Action", "Ce qui a changé"],
    "ar": ["التاريخ", "الشخص", "الإجراء", "ما تغيّر"],
}

SYSTEM_PERSON: dict[str, str] = {"en": "The system", "fr": "Le système", "ar": "النظام"}


def for_language(language: str) -> str:
    """Every dict above only has en/fr/ar: an unknown language falls back to English."""
    return language if language in ("en", "fr", "ar") else "en"
