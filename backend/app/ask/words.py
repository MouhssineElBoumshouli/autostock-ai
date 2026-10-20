"""Turning typed text into comparable words, for French, English, Arabic and Darija."""

import re
import unicodedata

ARABIC_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ـ": ""})

# Little words that never name a part, in the four languages.
LITTLE_WORDS = set(
    """
    how many much did do does we our us i you what whats which who are is was the a an of for in at on
    have has there any all part parts item items product products and it will to need should soon this that
    me my with by from category
    combien de d des du la le les l on a en au aux que qu quoi quelle quelles quel quels est ce ci sont
    ca je nous y t il pour dans qui va vont etre se plus piece pieces produit produits et mon nos notre
    passer categorie bientot
    كم من في ما هي هو التي الذي هل هناك ماذا يجب ان نحن لدينا عندنا قسم و على الى عن القطع المنتجات
    chhal ch7al chno achno ach li lli f fi mn men dyal wach kayna kayn chi had 3ndna ghadi khassni bzaf
    شحال اشنو اللي ف ديال واش كاين كاينه شي هاد غادي السلعه
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
    """Equal, or one typo away when both words are long enough for a typo to be clear."""
    if typed == known or without_article(typed) == without_article(known):
        return True
    return len(typed) >= 4 and len(known) >= 4 and edit_distance(typed, known) <= 1
