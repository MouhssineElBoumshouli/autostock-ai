"""The baseline way to understand a question: keyword lists, always available, no AI.

1. Words about things we can't answer (customers, staff, prices, changing data) -> cannot_answer.
2. Period, branch and question-type phrases are found (one clear typo forgiven) and removed.
3. What is left, minus little words, must be understood: category words, or words the shop's
   parts are called by (names, brands, synonym list). Then it is the category or the part.
Any word left that isn't understood, or no question-type phrase at all -> not sure: the person is
asked which of the closest question types they meant. The rule never guesses.
"""

from app.ask.question import CANNOT_ANSWER, NOT_SURE, QUESTION_TYPES, Question, ShopWords, checked_question
from app.ask.words import LITTLE_WORDS, normalize, same_word, words_of

OUT_OF_SCOPE = """customer customers client clients employee employees staff weather delete remove change price prices
    invoice invoices margin profit phone add
    meilleur employe supprime supprimer prix meteo facture marge benefice numero telephone ajoute ajouter
    زبون زبائن موظف عميل احذف حذف سعر طقس فاتوره هاتف رقم ربح اضف
    chkoun ahsan bdel lprix match lmatch r9m nmra""".split() + [
    # The app never orders by itself: a person does, on the Orders page.
    "place an order", "place the order", "passe une commande", "passer une commande", "passe commande", "passer commande",
    "اطلب لي", "دير كوموند", "dir commande", "dir lcommande"]

PERIOD_PHRASES = {
    "today": ["today", "aujourd hui", "ce jour", "اليوم", "ليوم", "lyouma", "lyoum", "lyom", "had nhar", "هاد النهار"],
    "yesterday": ["yesterday", "hier", "امس", "البارح", "البارحه", "lbare7", "lbareh"],
    "this_week": ["this week", "cette semaine", "هذا الاسبوع", "هاد الاسبوع", "had simana", "had smana",
                  "هاد السيمانه"],
    "last_week": ["last week", "past week", "previous week", "semaine derniere", "semaine passee",
                  "semaine precedente", "الاسبوع الماضي", "بالاسبوع الماضي", "الاسبوع الفائت", "simana li fatet",
                  "simana li fat", "السيمانه اللي فاتت", "السيمانه اللي دازت"],
    "this_month": ["this month", "ce mois", "du mois", "هذا الشهر", "هاد الشهر", "had chhar", "had ch7ar"],
    "last_month": ["last month", "past month", "previous month", "mois dernier", "mois passe", "mois precedent",
                   "الشهر الماضي", "بالشهر الماضي", "الشهر الفائت", "الشهر اللي فات", "chhar li fat", "chhar li fat"],
    "this_year": ["this year", "cette annee", "l annee", "هذه السنه", "هذا العام", "هاد العام", "had l3am"],
    None: ["next month", "next week", "mois prochain", "semaine prochaine", "الشهر القادم", "الشهر الجاي",
           "chhar jay", "simana jaya", "soon", "bientot", "prochainement", "قريبا"],
}

CITY_NAMES = {
    "casablanca": ["casablanca", "casa", "كازا", "الدار البيضاء", "dar lbida", "dar beida"],
    "rabat": ["rabat", "الرباط", "rbat"],
    "marrakech": ["marrakech", "marrakesh", "مراكش", "marrakch", "mraksh"],
}

# Checked in this order: the first type with a phrase in the question wins.
TYPE_PHRASES = [
    ("cannot_answer", OUT_OF_SCOPE),
    # Broad questions get today's briefing: sales vs a normal week, alerts, to order, late deliveries.
    ("today_briefing", ["going on", "whats new", "what s new", "how is the shop doing", "how are we doing",
                        "how is business", "summary", "briefing", "worry about", "quoi de neuf", "comment va",
                        "le point", "resume", "inquieter", "ach kayn", "achno kayn", "chno kayn", "chno jdid",
                        "kidayra", "kidayr", "kifach dayra", "ما الجديد", "ماذا يحدث", "كيف حال", "ملخص", "يقلقني",
                        "اش كاين", "اشنو كاين", "شنو كاين", "كيداير", "كيدايره", "شنو جديد"]),
    ("part_details", ["everything about", "all about", "details", "detail", "tout sur", "fiche", "infos",
                      "informations", "kolchi 3la", "تفاصيل", "كل شيء عن", "معلومات", "كلشي على"]),
    # "why" words are matched exactly (WHY_WORDS): "ماذا" (what) is one letter from "لماذا" (why).
    ("explain_part_change", ["explain", "explique", "اشرح"]),
    ("compare_branches", ["which branch", "what branch", "quelle agence", "quelle succursale", "quel magasin",
                          "each branch", "chaque agence", "اي فرع", "كل فرع", "ach men far3", "chmen far3",
                          "kol far3"]),
    ("late_deliveries", ["late", "overdue", "delayed", "not arrived", "retard", "pas arrive", "pas encore arrive",
                         "متاخر", "متاخره", "تاخر", "لم تصل", "m3etla", "m3atla", "t3etel", "ma wslat", "ma wslatch"]),
    ("open_alerts", ["alert", "alerts", "alerte", "alertes", "warning", "warnings", "flagged", "problem", "problems",
                     "anomalie", "anomalies", "probleme", "problemes", "تنبيه", "تنبيهات", "مشكل", "مشاكل",
                     "mochkil", "machakil"]),
    ("forecast_of_part", ["forecast", "prevision", "previsions", "predict", "prediction", "expect", "expected",
                          "think we ll sell", "will we sell", "we ll sell", "va vendre", "allons vendre", "توقعات",
                          "توقع", "نتوقع", "ghadi nbi3o", "غادي نبيعو"]),
    ("sales_vs_last", ["compared", "compare", "vs", "versus", "better than", "worse than", "par rapport",
                       "plus ou moins", "مقارنه", "ارتفعت", "انخفضت", "tla3", "habet", "kter wla 9al", "طلع", "هبط"]),
    ("what_to_order", ["order", "reorder", "commander", "commande", "recommander", "نطلب", "اطلب", "طلبه", "طلبيه",
                       "ncommandi", "الكوموند", "كوموند", "njibo", "nchriw"]),
    ("running_out", ["run out", "running out", "run low", "rupture", "manquer", "تنفد", "ستنفد", "النفاد", "نفاد",
                     "ysali", "يسالي", "ykmel", "يكمل"]),
    ("best_sellers", ["best sellers", "best seller", "best selling", "top selling", "top product", "top products",
                      "sold the most", "sells the most", "sell the most", "most sold", "meilleures ventes",
                      "plus vendus", "plus vendu", "part le plus", "se vend le plus", "الاكثر مبيعا", "اكثر مبيعا",
                      "بيعت اكثر", "kaytba3 bzaf", "كيتباع بزاف", "tba3 ktar", "تباع كثر"]),
    ("dead_stock", ["dead", "not selling", "not moving", "sitting on the shelf", "never sells", "ne se vendent plus",
                    "ne se vend pas", "dorment", "qui dort", "mort", "invendus", "الراكد", "راكد", "لا تباع", "لم تبع",
                    "ma kaytba3ch", "ma katbi3ch", "ناعسه", "bayta", "بايته", "ناعسين"]),
    ("stock_of_part", ["in stock", "stock", "stok", "left", "still have", "do we have", "remaining", "reste",
                       "il reste", "مخزون", "المخزون", "تبقى", "باقي", "عندنا", "لدينا", "3ndna", "3andna", "bqa",
                       "b9a", "بقا"]),
    ("sales_of", ["sell", "sold", "sales", "selling", "ventes", "vente", "vendu", "vendus", "vend", "بعنا", "مبيعات",
                  "بيع", "بيعت", "bi3na", "bi3", "tba3"]),
]

CATEGORY_WORDS = {
    "Filters": ["filters", "filtres", "filtration", "فلاتر"],
    "Oils": ["oils", "huiles", "lubrifiants", "زيوت"],
    "Ignition": ["ignition", "allumage", "اشعال"],
    "Brakes": ["brakes", "brake", "freinage", "freins", "frein", "فرامل", "فرانات", "فران", "frane", "fran"],
    "Lighting": ["lighting", "lights", "eclairage", "اضاءه", "ضو", "daw"],
    "Suspension": ["suspension", "تعليق"],
    "Engine": ["engine", "moteur", "محرك", "motor"],
    "Transmission": ["transmission", "ناقل الحركه"],
    "Electrical": ["electrical", "electricity", "electrique", "electricite", "كهرباء", "trisinti", "tricinti"],
    "Cooling": ["cooling", "refroidissement", "تبريد"],
    "Air conditioning": ["air conditioning", "clim", "climatisation", "تكييف", "مكيف"],
    "Visibility": ["visibility", "visibilite"],
}

# Words that only say "this is a follow-up": "and in Rabat?", "et à Casa ?", "w f rbat?", "وفي مراكش؟".
FOLLOW_UP_WORDS = set(words_of("and also what about how about et aussi pour w o wa fi f و وفي وف ف في"))
WHY_WORDS = set(words_of("why pourquoi 3lach 3lah lach علاش لماذا لاش علاه"))
FOLLOW_UP_MOST_WORDS = 5

# When unsure, the question types to offer, from what was understood.
SUGGEST_FOR_PART = ("stock_of_part", "sales_of", "forecast_of_part")
SUGGEST_FOR_CATEGORY = ("sales_of", "best_sellers", "what_to_order")
SUGGEST_FOR_PERIOD = ("sales_of", "best_sellers", "sales_vs_last")
SUGGESTIONS_SHOWN = 3


def read_with_rule(text: str, shop: ShopWords) -> Question:
    words = words_of(text)
    period, words = _take_period(words)
    branches, words = _take_branches(words, shop.branches)
    why = any(word in WHY_WORDS for word in words)
    question_type, words = _take_type([word for word in words if word not in WHY_WORDS])
    if question_type == "cannot_answer":
        return CANNOT_ANSWER
    if why and question_type in (None, "sales_of", "sales_vs_last"):
        question_type = "explain_part_change"  # "why are brake pad sales down?"
    if len(branches) > 1 and question_type in (None, "sales_of", "sales_vs_last", "compare_branches"):
        question_type = "compare_branches"  # "compare Casablanca and Rabat"
    if question_type == "sales_vs_last":
        period = {"last_week": "this_week", "last_month": "this_month", "yesterday": "today"}.get(period, period)
    branch = branches[0] if len(branches) == 1 else None

    left = [word for word in words if word not in LITTLE_WORDS]
    category, unknown = _subject(left, shop)
    part = " ".join(left) if left and category is None else None
    if question_type == "explain_part_change" and not part:
        question_type = "sales_vs_last"  # "why are sales down?" with no part: this period against the one before
    if question_type is None or unknown:
        return _not_sure(question_type, part, category, branch, period)

    allowed = QUESTION_TYPES[question_type]
    raw = {"type": question_type, "part": part, "category": category, "branch": branch, "period": period}
    return checked_question({k: v for k, v in raw.items() if k == "type" or k in allowed}, shop) or CANNOT_ANSWER


def read_follow_up(text: str, earlier: Question, shop: ShopWords) -> Question | None:
    """A short question that only changes the one before ("and in Rabat?", "et la semaine dernière ?",
    "w f casa?", "why?"), merged into it. None when it is a question of its own."""
    words = [word for word in words_of(text) if word not in FOLLOW_UP_WORDS]
    if len(words) > FOLLOW_UP_MOST_WORDS:
        return None
    why = any(word in WHY_WORDS for word in words)
    words = [word for word in words if word not in WHY_WORDS]
    period, words = _take_period(words)
    branches, words = _take_branches(words, shop.branches)
    question_type, words = _take_type(words)
    if question_type is not None or len(branches) > 1:
        return None
    left = [word for word in words if word not in LITTLE_WORDS]
    category, unknown = _subject(left, shop)
    if unknown:
        return None
    changes = {"period": period, "branch": branches[0] if branches else None, "category": category,
               "part": " ".join(left) if left and category is None else None}
    changes = {name: value for name, value in changes.items() if value}
    if not changes and not why:
        return None
    merged = {"type": earlier.type, **earlier.filters()}
    if "part" in changes or "category" in changes:
        merged.pop("part", None)
        merged.pop("category", None)
    merged.update(changes)
    if why and merged.get("part"):
        merged["type"] = "explain_part_change"  # "why?" about a part: what changed for it
    allowed = QUESTION_TYPES[merged["type"]]
    return checked_question({k: v for k, v in merged.items() if k == "type" or k in allowed}, shop)


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
            return True, words[:start] + words[start + len(normalize(phrase).split()):]
    return False, words


def _take_all(words: list[str], phrases: list[str]) -> tuple[bool, list[str]]:
    found_any = False
    while True:
        found, words = _take(words, phrases)
        if not found:
            return found_any, words
        found_any = True


def _take_period(words: list[str]) -> tuple[str | None, list[str]]:
    found_period = None
    for period, phrases in PERIOD_PHRASES.items():
        found, words = _take_all(words, phrases)
        if found and period and found_period is None:
            found_period = period
    return found_period, words


def _take_branches(words: list[str], branches: tuple[str, ...]) -> tuple[list[str], list[str]]:
    """Every branch named, in the shop's order, and the words left."""
    found = []
    for branch in branches:
        names = [w for w in words_of(branch) if len(w) >= 4]
        for city, aliases in CITY_NAMES.items():
            if city in names:
                names += aliases
        taken, words = _take_all(words, names)
        if taken:
            found.append(branch)
    return found, words


def _take_type(words: list[str]) -> tuple[str | None, list[str]]:
    """The first type with a phrase in the words. Every type phrase is removed, so words like
    "sales" in "best sellers... sales" never end up read as a part name."""
    found_type = None
    for question_type, phrases in TYPE_PHRASES:
        found, words = _take_all(words, phrases)
        if found and found_type is None:
            found_type = question_type
            if question_type == "cannot_answer":
                break
    return found_type, words


def _subject(left: list[str], shop: ShopWords) -> tuple[str | None, list[str]]:
    """(the category if every word left names it, words nobody understands)."""
    category = _category(left, shop.categories)
    if category:
        return category, []
    known = shop.part_words | _all_category_words(shop.categories)
    unknown = [word for word in left if not any(same_word(word, part_word) for part_word in known)]
    return None, unknown


def _category_words(category: str) -> list[str]:
    return [*words_of(category), *(w for phrase in CATEGORY_WORDS.get(category, []) for w in words_of(phrase))]


def _all_category_words(categories: tuple[str, ...]) -> set[str]:
    return {word for category in categories for word in _category_words(category)}


def _category(left: list[str], categories: tuple[str, ...]) -> str | None:
    """The shop category if every word left names it ("les filtres", "l'électrique")."""
    if not left:
        return None
    for category in categories:
        known = _category_words(category)
        if all(any(same_word(word, k) for k in known) for word in left):
            return category
    return None


def _not_sure(found_type, part, category, branch, period) -> Question:
    candidates = [found_type] if found_type else []
    if part:
        candidates += SUGGEST_FOR_PART
    if category:
        candidates += SUGGEST_FOR_CATEGORY
    if period:
        candidates += SUGGEST_FOR_PERIOD
    candidates += ["sales_of", "stock_of_part", "what_to_order"]
    suggestions = tuple(dict.fromkeys(candidates))[:SUGGESTIONS_SHOWN]
    return Question(NOT_SURE, part=part, category=category, branch=branch, period=period, suggestions=suggestions)


def branch_named(text: str, branches: tuple[str, ...]) -> str | None:
    """The shop branch `text` names ("rabat", "Casa", "الرباط"), or None."""
    if text in branches:
        return text
    found, _ = _take_branches(words_of(text), branches)
    return found[0] if found else None


def category_named(text: str, categories: tuple[str, ...]) -> str | None:
    """The shop category `text` names ("brakes", "les freins", "فرامل"), or None."""
    if text in categories:
        return text
    return _category([word for word in words_of(text) if word not in LITTLE_WORDS], categories)
