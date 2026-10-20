"""The baseline way to understand a question: keyword lists, always available, no AI.

1. Words about things we can't answer (customers, staff, prices, deleting) -> cannot_answer.
2. Period, branch and question-type phrases are found (one typo forgiven in long words) and removed.
3. What is left, minus little words, names a category (if it is one of the shop's) or a part.
No question-type phrase -> cannot_answer: the rule never guesses.
"""

from app.ask.question import CANNOT_ANSWER, QUESTION_TYPES, Question, ShopWords, checked_question
from app.ask.words import LITTLE_WORDS, normalize, same_word, without_article, words_of

OUT_OF_SCOPE = """customer customers client clients employee employees staff weather delete remove change price prices
    meilleur employe supprime supprimer prix meteo زبون زبائن موظف عميل احذف حذف سعر طقس
    chkoun ahsan bdel lprix match lmatch""".split()

PERIOD_PHRASES = {
    "today": ["today", "aujourd hui", "اليوم", "ليوم", "lyouma", "lyoum", "had nhar"],
    "yesterday": ["yesterday", "hier", "امس", "البارحه", "lbare7"],
    "this_week": ["this week", "cette semaine", "هذا الاسبوع", "had simana", "هاد السيمانه"],
    "last_week": ["last week", "semaine derniere", "semaine passee", "الاسبوع الماضي", "بالاسبوع الماضي",
                  "simana li fatet", "السيمانه اللي فاتت"],
    "this_month": ["this month", "ce mois", "هذا الشهر", "had chhar", "هاد الشهر"],
    "last_month": ["last month", "mois dernier", "mois passe", "الشهر الماضي", "الشهر اللي فات", "chhar li fat"],
    "this_year": ["this year", "cette annee", "هذه السنه", "هذا العام", "had l3am", "هاد العام"],
    None: ["next month", "mois prochain", "الشهر القادم", "الشهر الجاي", "chhar jay", "soon", "قريبا"],
}

CITY_NAMES = {
    "casablanca": ["casablanca", "casa", "كازا", "الدار البيضاء", "dar lbida"],
    "rabat": ["rabat", "الرباط"],
    "marrakech": ["marrakech", "marrakesh", "مراكش", "marrakch"],
}

# Checked in this order: the first type with a phrase in the question wins.
TYPE_PHRASES = [
    ("cannot_answer", OUT_OF_SCOPE),
    ("late_deliveries", ["late", "retard", "المتاخره", "متاخره", "m3etla", "t3etel", "m3atla"]),
    ("open_alerts", ["alert", "alerts", "alerte", "alertes", "تنبيه", "تنبيهات", "التنبيهات"]),
    ("forecast_of_part", ["forecast", "prevision", "previsions", "توقعات", "التوقعات", "will we sell", "va vendre",
                          "ghadi nbi3o", "غادي نبيعو"]),
    ("sales_vs_last", ["compared", "vs", "versus", "par rapport", "مقارنه", "tla3", "habet", "طلع"]),
    ("what_to_order", ["order", "commander", "commande", "نطلب", "اطلب", "ncommandi", "الكوموند", "كوموند"]),
    ("running_out", ["run out", "running out", "rupture", "manquer", "تنفد", "ستنفد", "ysali", "يسالي"]),
    ("best_sellers", ["best sellers", "best seller", "top selling", "most sold", "meilleures ventes", "plus vendus",
                      "الاكثر مبيعا", "kaytba3 bzaf", "كيتباع بزاف"]),
    ("dead_stock", ["dead", "not selling", "ne se vendent plus", "mort", "الراكد", "راكد", "لا تباع",
                    "ma kaytba3ch", "ناعسه"]),
    ("stock_of_part", ["in stock", "stock", "stok", "مخزون", "المخزون", "3ndna", "عندنا"]),
    ("sales_of", ["sell", "sold", "sales", "ventes", "vente", "vendu", "بعنا", "مبيعات", "bi3na", "بيع", "bi3"]),
]

CATEGORY_WORDS = {
    "Filters": ["filters", "filtres", "فلاتر"],
    "Oils": ["oils", "huiles", "زيوت"],
    "Ignition": ["ignition", "allumage", "اشعال"],
    "Brakes": ["brakes", "freinage", "فرامل", "فرانات", "frane"],
    "Lighting": ["lighting", "eclairage", "اضاءه"],
    "Suspension": ["suspension", "تعليق"],
    "Engine": ["engine", "moteur", "محرك"],
    "Transmission": ["transmission", "ناقل"],
    "Electrical": ["electrical", "electrique", "كهرباء", "trisinti"],
    "Cooling": ["cooling", "refroidissement", "تبريد"],
    "Air conditioning": ["climatisation", "تكييف", "clim"],
    "Visibility": ["visibility", "visibilite"],
}


def read_with_rule(text: str, shop: ShopWords) -> Question:
    words = words_of(text)
    period, words = _take_period(words)
    branch, words = _take_branch(words, shop.branches)
    question_type, words = _take_type(words)
    if question_type is None or question_type == "cannot_answer":
        return CANNOT_ANSWER
    if question_type == "sales_vs_last":
        period = {"last_week": "this_week", "last_month": "this_month", "yesterday": "today"}.get(period, period)

    raw: dict[str, str | None] = {"type": question_type, "branch": branch, "period": period}
    left = [word for word in words if word not in LITTLE_WORDS]
    category = _category(left, shop.categories)
    if category:
        raw["category"] = category
    elif left:
        raw["part"] = " ".join(left)
    allowed = QUESTION_TYPES[question_type]
    return checked_question({k: v for k, v in raw.items() if k == "type" or k in allowed}, shop) or CANNOT_ANSWER


def _find(words: list[str], phrase: str) -> int | None:
    """Where the phrase starts in the words, or None."""
    wanted = normalize(phrase).split()
    for start in range(len(words) - len(wanted) + 1):
        if all(same_word(words[start + i], w) for i, w in enumerate(wanted)):
            return start
    return None


def _take(words: list[str], phrases: list[str]) -> tuple[bool, list[str]]:
    """Removes the first phrase found (longest first) from the words."""
    for phrase in sorted(phrases, key=lambda p: -len(p.split())):
        start = _find(words, phrase)
        if start is not None:
            return True, words[:start] + words[start + len(phrase.split()):]
    return False, words


def _take_period(words: list[str]) -> tuple[str | None, list[str]]:
    found_period = None
    for period, phrases in PERIOD_PHRASES.items():
        found, words = _take(words, phrases)
        if found and period and found_period is None:
            found_period = period
    return found_period, words


def _take_branch(words: list[str], branches: tuple[str, ...]) -> tuple[str | None, list[str]]:
    for branch in branches:
        names = [w for w in words_of(branch) if len(w) >= 4]
        for city, aliases in CITY_NAMES.items():
            if city in names:
                names += aliases
        found, words = _take(words, names)
        if found:
            return branch, words
    return None, words


def _take_type(words: list[str]) -> tuple[str | None, list[str]]:
    for question_type, phrases in TYPE_PHRASES:
        found, rest = _take(words, phrases)
        if found:
            # Words of other types' phrases ("sales" in "best sellers... sales") never name a part.
            for _, other in TYPE_PHRASES[1:]:
                while True:
                    found_more, rest = _take(rest, other)
                    if not found_more:
                        break
            return question_type, rest
    return None, words


def _category(left: list[str], categories: tuple[str, ...]) -> str | None:
    """The shop category if every word left names it ("les filtres", "l'électrique")."""
    if not left:
        return None
    for category in categories:
        known = [*words_of(category), *CATEGORY_WORDS.get(category, [])]
        if all(any(same_word(without_article(word), without_article(normalize(k))) for k in known) for word in left):
            return category
    return None
