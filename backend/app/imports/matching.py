"""Suggests which field a column is, from its header alone, so new shops don't start from a blank form.

Free and local: no API, no internet, nothing leaves the shop's computer. Two ways are measured in
evaluate_matchers() against the headers in header_examples.py, and the better one is used by
suggest_field(). The person always sees the suggestion in the Match step and can change it before
anything is saved; this never fills in a field we aren't fairly confident about.
"""

import re
import unicodedata
from functools import lru_cache

from app.imports.fields import FIELDS, ImportKind
from app.imports.header_examples import PARTS_HEADER_SETS, SALES_HEADER_SETS

_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


def normalize_for_matching(header: str) -> str:
    """Lowercase, no punctuation, single spaces. Keeps accents and Arabic script (unlike
    normalize_header in values.py, which is only for exact-memory lookups in Latin scripts).
    """
    text = unicodedata.normalize("NFKC", header).replace("_", " ")
    return " ".join(_NON_WORD.sub(" ", text).lower().split())


# Checked in this order: the first field whose keywords appear in the header wins. More specific
# fields (an OEM reference, a minimum stock level) are checked before the generic ones they could
# be mistaken for (a SKU, a quantity).
_PARTS_ORDER = [
    "oem_reference", "min_stock", "unit_cost", "sale_price", "sku", "quantity", "branch", "supplier",
    "brand", "category", "name",
]
_SALES_ORDER = ["date", "sku", "unit_price", "quantity", "branch"]

_KEYWORDS: dict[ImportKind, dict[str, list[str]]] = {
    "parts": {
        "oem_reference": [
            "oem", "constructeur", "original reference", "mfr reference", "manufacturer reference", "صانع",
            "المرجع الأصلي",
        ],
        "min_stock": [
            "stock mini", "stock min", "min stock", "min qty", "minimum", "seuil", "reorder", "safety stock",
            "mini", "الحد الأدنى", "ادنى", "أدنى",
        ],
        "unit_cost": ["achat", "cost", "buy price", "purchase price", "purchase", "cout", "سعر الشراء", "تكلفة", "الشراء"],
        "sale_price": ["vente", "sale", "sell", "retail", "pv ttc", "price", "سعر البيع", "سعر"],
        "sku": [
            "sku", "ref", "réf", "reference", "référence", "code", "part no", "item code", "product code", "رمز",
            "كود", "مرجع",
        ],
        "quantity": [
            "quantity", "qty", "qte", "qté", "stock", "on hand", "disponible", "dispo", "الكمية", "متوفر",
        ],
        "branch": [
            "branch", "warehouse", "depot", "dépôt", "site", "store", "location", "loc", "entrepot", "entrepôt",
            "succursale", "magasin", "dep", "الفرع", "مستودع",
        ],
        "supplier": ["supplier", "vendor", "fournisseur", "المورد", "مزود"],
        "brand": ["brand", "marque", "manufacturer", "mfr", "make", "الماركة", "ماركة", "العلامة"],
        "category": ["category", "categorie", "catégorie", "famille", "family", "type", "cat", "الفئة", "تصنيف", "نوع"],
        "name": [
            "name", "design", "designation", "désignation", "nom", "description", "desc", "title", "libelle",
            "libellé", "الاسم", "اسم", "وصف", "تسمية",
        ],
    },
    "sales": {
        "date": ["date", "jour", "day", "التاريخ", "تاريخ", "يوم"],
        "sku": [
            "sku", "ref", "réf", "reference", "référence", "code", "part no", "item code", "product code", "رمز",
            "كود", "مرجع",
        ],
        "unit_price": ["unit price", "price per unit", "prix unitaire", "pu ttc", "prix", "price", "ثمن", "سعر"],
        "quantity": [
            "quantity", "qty", "qte", "qté", "sold", "vendue", "vendus", "nombre", "عدد", "الكمية", "مباعة",
        ],
        "branch": [
            "branch", "warehouse", "depot", "dépôt", "site", "store", "location", "loc", "entrepot", "entrepôt",
            "succursale", "magasin", "الفرع", "مستودع",
        ],
    },
}
_ORDERS: dict[ImportKind, list[str]] = {"parts": _PARTS_ORDER, "sales": _SALES_ORDER}


def keyword_match(header: str, kind: ImportKind) -> str | None:
    """The simple, explainable baseline: does the header contain a word we know for this field?"""
    text = normalize_for_matching(header)
    keywords = _KEYWORDS[kind]
    for field in _ORDERS[kind]:
        if any(word in text for word in keywords[field]):
            return field
    return None


def _flat_examples(kind: ImportKind, sets: list[list[tuple[str, str | None]]]) -> list[tuple[str, str]]:
    """(header, field) pairs, "ignore" standing in for None so scikit-learn has one label type."""
    return [(header, field or "ignore") for row in sets for header, field in row]


# The last few header sets of each kind are kept out of training, so the score on them means
# something: how well a matcher does on a file shaped unlike anything it learned from.
_TRAIN_TEST: dict[ImportKind, tuple[list, list]] = {
    "parts": (PARTS_HEADER_SETS[:12], PARTS_HEADER_SETS[12:]),
    "sales": (SALES_HEADER_SETS[:10], SALES_HEADER_SETS[10:]),
}


@lru_cache
def _trained_model(kind: ImportKind):
    """A small pipeline: character n-grams (robust to typos and short words) plus logistic
    regression. Trained once per process on ~250 labeled headers; fast enough to do at import time.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    train_sets, _ = _TRAIN_TEST[kind]
    examples = _flat_examples(kind, train_sets)
    headers = [normalize_for_matching(header) for header, _ in examples]
    labels = [field for _, field in examples]
    model = Pipeline(
        [
            ("features", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)),
            ("classify", LogisticRegression(max_iter=2000)),
        ]
    )
    model.fit(headers, labels)
    return model


def model_match(header: str, kind: ImportKind) -> str | None:
    """The scikit-learn baseline. Predicts a field even for a column we should ignore, so we only
    trust it when it is confident; otherwise we leave the column unmatched, same as the keyword rule.
    """
    model = _trained_model(kind)
    text = normalize_for_matching(header)
    [probabilities] = model.predict_proba([text])
    best_index = probabilities.argmax()
    label = model.classes_[best_index]
    if label == "ignore" or probabilities[best_index] < 0.5:
        return None
    return label


def evaluate_matchers() -> dict[ImportKind, dict[str, float]]:
    """Accuracy of each matcher on the held-out test headers of each kind, as a fraction correct."""
    results: dict[ImportKind, dict[str, float]] = {}
    for kind, (_, test_sets) in _TRAIN_TEST.items():
        examples = _flat_examples(kind, test_sets)
        keyword_correct = sum(1 for header, field in examples if (keyword_match(header, kind) or "ignore") == field)
        model_correct = sum(1 for header, field in examples if (model_match(header, kind) or "ignore") == field)
        total = len(examples)
        results[kind] = {
            "keyword_rule": keyword_correct / total,
            "scikit_learn": model_correct / total,
            "examples": total,
        }
    return results


# Measured once with evaluate_matchers() and written to docs/journey.md; whichever scored better
# overall is the one suggest_field() uses. Both are kept in the code so this stays easy to re-check.
# The keyword rule won clearly (it does not need to generalize from a small number of examples the
# way the model does), so it is the one used. Like a forecast that doesn't beat its baseline, the
# weaker approach is kept in the code only for comparison, never used to make real suggestions.
_USE_MODEL = False


def suggest_field(header: str, kind: ImportKind) -> str | None:
    """A column's likely field, or None to leave it for the person to choose. Never applied by
    itself: it only pre-fills the Match step, which the person always reviews before saving.
    """
    known = {field.key for field in FIELDS[kind]}
    guess = model_match(header, kind) if _USE_MODEL else keyword_match(header, kind)
    return guess if guess in known else None
