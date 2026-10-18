"""Finds parts the way a counter employee types: typos, part numbers written differently,
French, English, Arabic or Darija.

How a search is scored:
- Part numbers (SKU or OEM) are compared without spaces, dashes, dots or case. An exact match
  always comes first, then part numbers that contain what was typed.
- Words are normalized in the database (search_text, see migration 0006), then grouped into
  "concepts" using the shop's synonym list: "brake pads" also looks for "plaquettes de frein".
- A concept scores 1 when the part's name, brand or category has one of its words (or a word
  starting with it: "amort" finds "amortisseur"), else 0.
- A typed word found in no part at all may be a typo: it then scores how alike it is to the
  part's words (pg_trgm word similarity, 0 to 1), using the trigram index.
- The part's score is the average over all concepts, so a part matching every word comes first.
  Parts far below the best match are left out.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import Float, Subquery, Uuid, bindparam, case, false, func, literal, or_, select, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from app.models import Part, SynonymGroup

# Little words that would only add noise to the average.
STOP_WORDS = {"a", "au", "aux", "d", "de", "des", "du", "en", "et", "l", "la", "le", "les", "pour",
              "and", "for", "of", "the", "with", "ديال", "د", "في", "و"}
WORD_MATCH = 0.5  # how alike a typed word must be to a word of the part to bring the part up
MIN_SCORE = 0.4  # how well a part must match all typed words together to be shown
NEAR_BEST = 0.6  # ...and how close to the best match: "rear brake pads" doesn't list every "rear" part
EXACT_CODE = 10
PARTIAL_CODE = 5


@dataclass
class Concept:
    typed: str  # what the person typed, normalized
    words: list[str]  # the typed words and their synonyms


@dataclass
class PreparedSearch:
    code: str
    concepts: list[Concept]


def prepare(db: Session, organization_id: uuid.UUID, search: str) -> PreparedSearch:
    words, code = db.execute(select(func.search_text(search), func.search_code(search))).one()
    synonyms = db.execute(
        select(SynonymGroup.id, func.search_text(func.unnest(SynonymGroup.words)))
        .where(SynonymGroup.organization_id == organization_id)
    ).all()
    groups: dict[uuid.UUID, list[str]] = {}
    for group_id, phrase in synonyms:
        if phrase and phrase not in groups.setdefault(group_id, []):
            groups[group_id].append(phrase)
    return PreparedSearch(code=code, concepts=concepts_of(words.split(), list(groups.values())))


def concepts_of(words: list[str], groups: list[list[str]]) -> list[Concept]:
    """Splits normalized words into concepts. At each word, the longest synonym phrase that
    starts there wins and brings its whole group; other words stand alone. Stop words are
    dropped unless nothing else is left."""
    phrases: dict[tuple[str, ...], list[str]] = {}
    for group in groups:
        for phrase in group:
            phrases.setdefault(tuple(phrase.split()), group)
    longest = max((len(key) for key in phrases), default=0)

    concepts: list[Concept] = []
    position = 0
    while position < len(words):
        for size in range(min(longest, len(words) - position), 0, -1):
            typed = words[position:position + size]
            group = phrases.get(tuple(typed))
            if group:
                concepts.append(Concept(typed=" ".join(typed), words=group))
                position += size
                break
        else:
            if words[position] not in STOP_WORDS:
                concepts.append(Concept(typed=words[position], words=[words[position]]))
            position += 1
    return concepts or [Concept(typed=word, words=[word]) for word in words]


def is_code_like(code: str) -> bool:
    return len(code) >= 4 and any(character.isdigit() for character in code)


def forgives_typos(typed: str) -> bool:
    """Typos are looked for only in real words: 4 letters or more, no digits ("60", "5w30" must match)."""
    return len(typed) >= 4 and not any(character.isdigit() for character in typed)


def has_word(phrase: str):
    """The part has this word, or a word starting with it. search_words starts with a space,
    so one cheap LIKE " phrase" does it."""
    return Part.search_words.contains(f" {phrase}", autoescape=True)


def find_parts(db: Session, organization_id: uuid.UUID, search: str) -> list[tuple[uuid.UUID, float]]:
    """(part id, score) for every part of this shop that matches, best first."""
    prepared = prepare(db, organization_id, search)
    concepts, code = prepared.concepts, prepared.code
    exact_code = or_(Part.sku_key == code, Part.oem_key == code) if code else false()
    partial_code = or_(Part.sku_key.contains(code), Part.oem_key.contains(code)) if is_code_like(code) else false()
    code_score = case((exact_code, EXACT_CODE), (partial_code, PARTIAL_CODE), else_=0)
    has_concept = [or_(*[has_word(word) for word in concept.words]) for concept in concepts]

    # First pass, cheap: part numbers and words found as typed (or as a synonym).
    code_scores: dict[uuid.UUID, int] = {}
    concept_scores: dict[uuid.UUID, list[float]] = {}
    for part_id, part_code_score, *found in db.execute(
        select(Part.id, code_score, *has_concept)
        .where(Part.organization_id == organization_id, or_(exact_code, partial_code, *has_concept))
    ):
        code_scores[part_id] = part_code_score
        concept_scores[part_id] = [1.0 if hit else 0.0 for hit in found]

    # Second pass, only for typed words found nowhere in the shop: they may be typos.
    unknown = [
        index for index, concept in enumerate(concepts)
        if forgives_typos(concept.typed) and not any(scores[index] for scores in concept_scores.values())
    ]
    if unknown:
        db.execute(text(f"SET LOCAL pg_trgm.word_similarity_threshold = {WORD_MATCH}"))
        typed = [concepts[index].typed for index in unknown]
        for part_id, *similarities in db.execute(
            select(Part.id, *[func.word_similarity(word, Part.search_words) for word in typed])
            .where(Part.organization_id == organization_id, or_(*[literal(word).op("<%")(Part.search_words) for word in typed]))
        ):
            scores = concept_scores.setdefault(part_id, [0.0] * len(concepts))
            for index, similarity in zip(unknown, similarities):
                scores[index] = similarity

    found = []
    for part_id, scores in concept_scores.items():
        words_score = sum(scores) / len(scores) if scores else 0.0
        part_code_score = code_scores.get(part_id, 0)
        if part_code_score or words_score >= MIN_SCORE:
            found.append((part_id, part_code_score + words_score))
    best = max((score for _, score in found), default=0.0)
    return sorted([match for match in found if match[1] >= best * NEAR_BEST], key=lambda match: match[1], reverse=True)


def as_table(matches: list[tuple[uuid.UUID, float]]) -> Subquery:
    """The matches as a small table (part_id, score) other queries can join."""
    ids = bindparam("matched_ids", [part_id for part_id, _ in matches], type_=ARRAY(Uuid))
    scores = bindparam("matched_scores", [score for _, score in matches], type_=ARRAY(Float))
    return select(func.unnest(ids).label("part_id"), func.unnest(scores).label("score")).subquery()
