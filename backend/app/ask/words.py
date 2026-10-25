"""Turning typed text into comparable words, for French, English, Arabic and Darija."""

import re
import unicodedata

ARABIC_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ـ": ""})

# Little words that never name a part, in the four languages. "s re ll ve m" are what is left of
# "what's", "we're", "we'll", "we've", "I'm" once the apostrophe is gone.
LITTLE_WORDS = set(
    """
    how many much did do does we our us i you your what whats which who are is was were be the a an of for in at
    on have has there any anything something some all part parts item items product products stuff and or it its
    will would to need should soon this that these those me my with by from about can could please total overall
    category department section shelf amount number count delivery deliveries supplier suppliers
    cost costs money
    s re ll ve m
    combien de d des du la le les l on a en au aux que qu quoi quelle quelles quel quels est ce ci cet cette sont
    ca c je j nous vous y t il ils elle pour dans qui va vont etre se plus moins piece pieces produit produits
    article articles et ou mon ma mes nos notre votre passer categorie bientot rayon famille total montant nombre
    faut svp sur par avec livraison livraisons fournisseur fournisseurs
    cout coute couter
    كم من في ما هي هو التي الذي هل هناك ماذا يجب ان نحن لدينا عندنا قسم و على الى عن القطع المنتجات قطعه
    قطع اي او مع كل اجمالي مجموع عدد المورد الموردين مورد موردين التوصيلات توصيل
    التكلفه تكلفه
    chhal ch7al chno achno ach li lli l f fi mn men dyal d wach kayna kayn chi had 3ndna ghadi khassni bzaf
    3la ila w o sel3a lw
    شحال اشنو شنو اللي لي ف ديال واش كاين كاينه شي هاد غادي السلعه سلعه
    """.split()
)


def normalize(text: str) -> str:
    """Lower case, no accents or Arabic vowel marks, one Arabic spelling, no punctuation."""
    text = unicodedata.normalize("NFKD", text.lower().translate(ARABIC_LETTERS))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


def words_of(text: str) -> list[str]:
    return normalize(text).split()


def without_article(word: str) -> str:
    """"الفرامل" -> "فرامل": the Arabic "the" is glued to the word."""
    return word[2:] if word.startswith("ال") and len(word) > 4 else word


def word_root(word: str) -> str:
    """A rough root, so plurals meet singulars: "filtres"/"filtre", "بطاريات"/"بطاريه"."""
    word = without_article(word)
    for ending in ("ات", "ه"):
        if word.endswith(ending) and len(word) > len(ending) + 2:
            return word[: -len(ending)]
    return word[:-1] if word.endswith(("s", "x")) and len(word) > 3 else word


def content_key(text: str) -> frozenset[str]:
    """The words that matter, for comparing two ways of naming the same part."""
    return frozenset(without_article(word) for word in words_of(text) if word not in LITTLE_WORDS)


def edit_distance(first: str, second: str) -> int:
    previous = list(range(len(second) + 1))
    for i, a in enumerate(first, 1):
        current = [i]
        for j, b in enumerate(second, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def same_word(typed: str, known: str) -> bool:
    """Equal (or the same root), or one typo away when a typo is clear: the shorter word has 4
    letters or more and the longer one 5 or more ("stok" is "stock", but "most" is not "mort")."""
    if typed == known or word_root(typed) == word_root(known):
        return True
    shorter, longer = sorted((len(typed), len(known)))
    return shorter >= 4 and longer >= 5 and edit_distance(typed, known) <= 1


def vocabulary(phrases) -> frozenset[str]:
    """Every word of these phrases that could name something (no little words)."""
    return frozenset(word for phrase in phrases if phrase for word in words_of(phrase) if word not in LITTLE_WORDS)
