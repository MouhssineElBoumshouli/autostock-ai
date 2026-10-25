"""Checks the writer's text before anyone sees it, then puts the real numbers in.

The writer never types numbers: it writes labels ([F1]) for the facts it was given. A sentence is
let out only when:
- it has no number typed by the model (digits, Arabic digits or number words). Part names copied
  exactly ("5W30", "Golf 7") are not numbers; Darija spelling digits ("3tini") are letters;
- every label is a fact it was given;
- every label sits next to its own branch, part and period, and a change next to its own direction:
  of the nearest one named before it and the nearest after it (in its clause, else its sentence, never
  past the labels on either side), one must be the fact's own.
  "Casablanca [F8]" fails when [F8] is Rabat's; "down [F5]" fails when [F5] went up.
Then each label is replaced by its fact's number, formatted for the answer's language.
The first sentence that fails stops the answer; the website shows the app's own answer instead.
"""

import re
from dataclasses import dataclass

from app.ask.keyword_rule import branch_phrases
from app.ask.labeled_facts import Fact
from app.ask.number_check import numbers_written
from app.ask.words import LITTLE_WORDS, words_of

SENTENCE_END = re.compile(r"[.!?؟](?=\s)|\n")
LABEL = re.compile(r"\[\s*(F\d+)\s*\]|\b(F\d+)\b")
CLAUSE_MARK = re.compile(r"[,،;()–—]")
MOST_WAITING = 600  # characters with no sentence end: a model stuck repeating itself is stopped
ARABIC_PREFIXES = "وبلف"  # glued to the next word: "والرباط" is "and Rabat"
# Words saying which way a change went: next to a percentage, they must match it.
DIRECTION_PHRASES = {
    "up": ["up", "more", "higher", "increase", "increased", "rose", "grew", "hausse", "plus", "augmente", "augmentation",
           "progression", "ارتفاع", "ارتفعت", "زياده", "زادت", "اكثر", "tla3", "tal3", "طلع", "زاد"],
    "down": ["down", "less", "fewer", "lower", "decrease", "decreased", "dropped", "fell", "drop", "baisse", "moins",
             "diminue", "diminution", "recul", "chute", "انخفاض", "انخفضت", "تراجع", "نقص", "اقل", "tay7", "na9es",
             "habet", "هبط", "طاح", "نقصات"],
    "same": ["same", "stable", "unchanged", "pareil", "inchange", "نفس", "مستقر", "kif kif"],
}
# The words naming each period kind, longest first so "last year" isn't read as "last".
WHEN_PHRASES = {
    "last_year": ["last year", "same days last year", "a year ago", "an dernier", "annee derniere", "annee passee",
                  "السنه الماضيه", "العام الماضي", "l3am li fat", "العام اللي فات"],
    "normal": ["normal", "normale", "usual", "habituelle", "habituel", "average", "moyenne", "عادي", "العادي",
               "المعتاد", "متوسط"],
    "before": ["before", "previous", "last week", "last month", "last period", "earlier", "avant", "precedent", "precedente",
               "semaine derniere", "mois dernier", "derniere", "dernier", "السابق", "السابقه", "الماضي", "الماضيه",
               "قبل", "li fat", "اللي فات", "اللي فاتت"],
    "now": ["this week", "this month", "this year", "this period", "today", "now", "cette semaine", "ce mois",
            "cette annee", "cette periode", "aujourd hui", "maintenant", "هذا الاسبوع", "هذا الشهر", "هذه السنه",
            "هذه الفتره", "اليوم", "الان", "هاد السيمانه", "هاد الشهر", "daba", "دابا", "had simana", "had chhar"],
}


# When the question is about a past period ("le mois dernier"), its words name the period asked
# about ("this period" in the facts), not the one before it.
ASKED_PERIOD_PHRASES = {
    "yesterday": ["yesterday", "hier", "امس", "البارح"],
    "last_week": ["last week", "semaine derniere", "الاسبوع الماضي", "simana li fatet"],
    "last_month": ["last month", "mois dernier", "الشهر الماضي", "chhar li fat"],
}


@dataclass(frozen=True)
class Mention:
    at: int  # word position
    kind: str  # "branch", "part", "when" or "direction"
    name: str


class FactText:
    """Holds the writer's text until a sentence is complete, checks it, and lets it out with the real
    numbers in place of the labels. After the first problem it lets nothing more out."""

    def __init__(self, facts: list[Fact], branches: tuple[str, ...], period: str | None = None):
        self.facts = {fact.label: fact for fact in facts}
        self.names = _names_with_digits(facts)
        # Numbers in the facts' own descriptions ("within 14 days", "the next 30 days") come from the app.
        self.described = {number for fact in facts for number in numbers_written(fact.what)}
        self.vocabulary = _vocabulary(facts, branches, period)
        self.waiting = ""
        self.shown = ""
        self.wrong: list[str] = []

    def add(self, piece: str) -> str:
        self.waiting += piece
        ends = list(SENTENCE_END.finditer(self.waiting))
        if ends:
            return self._let_out(ends[-1].end())
        if len(self.waiting) > MOST_WAITING:
            self.wrong = self.wrong or ["(no end to the sentence)"]
        return ""

    def finish(self) -> str:
        return self._let_out(len(self.waiting))

    def _let_out(self, upto: int) -> str:
        if self.wrong:
            return ""
        ready, self.waiting = self.waiting[:upto], self.waiting[upto:]
        self.wrong = self.problems(ready)
        if self.wrong:
            return ""
        out = LABEL.sub(lambda found: self.facts[found.group(1) or found.group(2)].shown, ready)
        self.shown += out
        return out

    def problems(self, text: str) -> list[str]:
        labels = [found.group(1) or found.group(2) for found in LABEL.finditer(text)]
        unknown = [label for label in labels if label not in self.facts]
        if unknown:
            return [f"unknown label {label}" for label in unknown]
        typed = [number for number in numbers_written(self._without_names(LABEL.sub(" ", text)))
                 if number not in self.described]
        if typed:
            return [f"typed number {number}" for number in typed]
        return self._misplaced(text)

    def _without_names(self, text: str) -> str:
        for name in self.names:
            text = re.sub(re.escape(name), " ", text, flags=re.IGNORECASE)
        return text

    def _misplaced(self, text: str) -> list[str]:
        marked = LABEL.sub(lambda found: f" zz{(found.group(1) or found.group(2)).lower()}zz ", text)
        marked = CLAUSE_MARK.sub(" zzclausezz ", SENTENCE_END.sub(" zzendzz ", marked))
        words = words_of(marked)
        places = []
        clause_number = sentence_number = 0
        for word in words:
            if word == "zzendzz":
                sentence_number += 1
                clause_number += 1
            elif word == "zzclausezz":
                clause_number += 1
            places.append((clause_number, sentence_number))
        mentions = self._mentions(words)
        labels = [(at, word[2:-2].upper()) for at, word in enumerate(words) if word.startswith("zzf") and word.endswith("zz")]
        problems = []
        for number, (at, label) in enumerate(labels):
            fact = self.facts[label]
            after_previous = labels[number - 1][0] if number else -1
            before_next = labels[number + 1][0] if number + 1 < len(labels) else len(words)
            for kind, own in (("branch", fact.branch), ("part", fact.part), ("when", fact.when),
                              ("direction", fact.direction)):
                if not own:
                    continue
                around = [m for m in mentions if m.kind == kind and after_previous < m.at < before_next]
                sides = _sides(at, around, places)
                if sides and own not in [mention.name for mention in sides]:
                    problems.append(f"[{label}] is {own}, written next to {sides[0].name}")
        return problems

    def _mentions(self, words: list[str]) -> list[Mention]:
        found, used = [], set()
        for kind, name, phrase in self.vocabulary:
            size = len(phrase)
            for start in range(len(words) - size + 1):
                span = range(start, start + size)
                if not used.intersection(span) and all(_same(words[start + i], phrase[i]) for i in range(size)):
                    found.append(Mention(start, kind, name))
                    used.update(span)
        return found


def _same(word: str, wanted: str) -> bool:
    return word == wanted or (len(word) > 3 and word[0] in ARABIC_PREFIXES and word[1:] == wanted)


def _sides(at: int, mentions: list[Mention], places: list[tuple[int, int]]) -> list[Mention]:
    """The nearest mention before the label and the nearest after it, in its clause, else in its
    sentence (only up to the labels on either side). The label is fine if either one is its own:
    "Rabat sold [F1]" and "[F1] pieces in Rabat" both read right."""
    for level in (0, 1):
        here = [m for m in mentions if places[m.at][level] == places[at][level]]
        before = [m for m in here if m.at < at]
        after = [m for m in here if m.at > at]
        sides = ([max(before, key=lambda m: m.at)] if before else []) + ([min(after, key=lambda m: m.at)] if after else [])
        if sides:
            return sides
    return []


def _vocabulary(facts: list[Fact], branches: tuple[str, ...], period: str | None) -> list[tuple[str, str, list[str]]]:
    """(kind, name, words) for every branch, every part the facts are about, and every period kind,
    longest phrases first."""
    phrases = [("branch", branch, words_of(phrase)) for branch in branches for phrase in branch_phrases(branch)]
    parts = sorted({fact.part for fact in facts if fact.part})
    shared = set.intersection(*(set(words_of(part)) for part in parts)) if len(parts) > 1 else set()
    for part in parts:
        own = [word for word in words_of(part) if word not in shared and word not in LITTLE_WORDS and not word.isdigit()]
        phrases += [("part", part, [word]) for word in own]
    asked = ASKED_PERIOD_PHRASES.get(period or "", [])
    phrases += [("when", "now", words_of(phrase)) for phrase in asked]
    phrases += [("when", kind, words_of(phrase)) for kind, kind_phrases in WHEN_PHRASES.items() for phrase in kind_phrases
                if phrase not in asked]
    phrases += [("direction", kind, words_of(phrase)) for kind, kind_phrases in DIRECTION_PHRASES.items()
                for phrase in kind_phrases]
    return sorted(phrases, key=lambda phrase: -len(phrase[2]))


def _names_with_digits(facts: list[Fact]) -> list[str]:
    """Pieces of the facts' part names that hold digits: "5W30", "DEMO-0050", "Picanto 1.0", "Golf 7 2.0".
    Copying them is naming a part, not typing a number. A lone digit is never a name."""
    found = set()
    for part in {fact.part for fact in facts if fact.part}:
        words = re.findall(r"[\w.-]+", part)
        for at, word in enumerate(words):
            if not re.search(r"\d", word):
                continue
            if re.search(r"[^\W\d]", word):
                found.add(word)
            start = at
            while start > 0 and re.search(r"\d", words[start - 1]):
                start -= 1
            if start > 0:
                found.add(" ".join(words[start - 1:at + 1]))
    return sorted(found, key=len, reverse=True)
