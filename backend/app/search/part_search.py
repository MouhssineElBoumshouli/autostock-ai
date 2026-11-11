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
  Parts far below the best match are left out. With every_word (Ask), when some parts match every
  word only they are kept: "filtre à huile dacia logan" is the Logan's oil filter, never every Logan
  part or every oil filter (the search screen keeps the near matches after them).
- If nothing matches well, the closest parts are offered instead of an empty list.
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
CLOSEST_MATCH = 0.4  # how alike a word must be to be offered as a closest guess
CLOSEST_SHOWN = 10
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
    """Splits normalized words into concepts using the word list. Little words are ignored when
    comparing ("plaquettes frein" = "plaquettes de frein"). At each word, in this order:
    1. the longest phrase of the list typed exactly;
    2. the longest phrase typed with typos ("plaquete frein");
    3. a word that starts a phrase ("plaquettes" -> "plaquettes de frein"), exact then with typos.
    Every matching group is used, and a word matched by none stands alone."""
    phrases = [(content_words(phrase.split()), group) for group in groups for phrase in group]
    phrases = [(key, group) for key, group in phrases if key]
    content = content_words(words)
    longest = max((len(key) for key, _ in phrases), default=0)

    concepts: list[Concept] = []
    position = 0
    while position < len(content):
        size, matched = _best_match(content[position:position + longest], phrases)
        typed = content[position:position + size]
        concepts.append(Concept(typed=" ".join(typed), words=_unique([" ".join(typed), *matched])))
        position += size
    return concepts


def content_words(words: list[str]) -> list[str]:
    """The words without little words, unless nothing else is left."""
    return [word for word in words if word not in STOP_WORDS] or words


def _best_match(ahead: list[str], phrases: list[tuple[list[str], list[str]]]) -> tuple[int, list[str]]:
    """How many typed words the best phrase covers, and the words of every group it matched."""
    for same in (_same_word, _alike_word):
        for size in range(len(ahead), 0, -1):
            groups = [group for key, group in phrases if len(key) == size and all(map(same, ahead[:size], key))]
            if groups:
                return size, [word for group in groups for word in group]
    for same in (_same_word, _alike_word):
        groups = [group for key, group in phrases if len(key) > 1 and same(ahead[0], key[0])]
        if groups:
            return 1, [word for group in groups for word in group]
    return 1, []


def _same_word(typed: str, word: str) -> bool:
    return typed == word


def _alike_word(typed: str, word: str) -> bool:
    return typed == word or (forgives_typos(typed) and trigram_similarity(typed, word) >= WORD_MATCH)


def trigram_similarity(first: str, second: str) -> float:
    """Shared groups of 3 letters over all groups, like pg_trgm: "demareur" ~ "demarreur" = 0.73."""
    first_set, second_set = _trigrams(first), _trigrams(second)
    return len(first_set & second_set) / len(first_set | second_set) if first_set | second_set else 0.0


def _trigrams(word: str) -> set[str]:
    padded = f"  {word} "
    return {padded[index:index + 3] for index in range(len(padded) - 2)}


def _unique(words: list[str]) -> list[str]:
    return list(dict.fromkeys(words))


def is_code_like(code: str) -> bool:
    return len(code) >= 4 and any(character.isdigit() for character in code)


def forgives_typos(typed: str) -> bool:
    """Typos are looked for only in real words: 4 letters or more, no digits ("60", "5w30" must match)."""
    return len(typed) >= 4 and not any(character.isdigit() for character in typed)


def has_word(phrase: str):
    """The part has this word, or a word starting with it. search_words starts with a space,
    so one cheap LIKE " phrase" does it."""
    return Part.search_words.contains(f" {phrase}", autoescape=True)


@dataclass
class SearchResult:
    matches: list[tuple[uuid.UUID, float]]  # (part id, score), best first
    closest: bool  # nothing matched well: these are the closest guesses


def find_parts(db: Session, organization_id: uuid.UUID, search: str, every_word: bool = False) -> SearchResult:
    prepared = prepare(db, organization_id, search)
    in_shop = Part.organization_id == organization_id
    code_scores, concept_scores = _match_codes_and_words(db, in_shop, prepared)

    # Typed words found nowhere in the shop may be typos.
    concepts = prepared.concepts
    unknown = [
        index for index, concept in enumerate(concepts)
        if forgives_typos(concept.typed) and not any(scores[index] for scores in concept_scores.values())
    ]
    _add_alike_words(db, in_shop, concepts, unknown, concept_scores, WORD_MATCH)

    scores = {part_id: code_scores.get(part_id, 0) + _average(found) for part_id, found in concept_scores.items()}
    matches = {part_id: score for part_id, score in scores.items() if code_scores.get(part_id) or score >= MIN_SCORE}
    if matches:
        full = {part_id for part_id in matches if _average(concept_scores[part_id]) >= 1}
        if every_word and full:
            matches = {part_id: score for part_id, score in matches.items() if part_id in full or code_scores.get(part_id)}
        best = max(matches.values())
        return SearchResult(_best_first({p: s for p, s in matches.items() if s >= best * NEAR_BEST}), closest=False)

    # Nothing matched well: show the closest parts rather than an empty list.
    if not any(scores.values()):
        typo_words = [index for index, concept in enumerate(concepts) if forgives_typos(concept.typed)]
        _add_alike_words(db, in_shop, concepts, typo_words, concept_scores, CLOSEST_MATCH)
        scores = {part_id: _average(found) for part_id, found in concept_scores.items()}
        scores.update(_alike_codes(db, in_shop, prepared.code))
    closest = {part_id: score for part_id, score in scores.items() if score > 0}
    return SearchResult(_best_first(closest)[:CLOSEST_SHOWN], closest=bool(closest))


def _match_codes_and_words(db: Session, in_shop, prepared: PreparedSearch):
    """Cheap first pass: part numbers, and words found as typed or through the word list."""
    code = prepared.code
    exact_code = or_(Part.sku_key == code, Part.oem_key == code) if code else false()
    partial_code = or_(Part.sku_key.contains(code), Part.oem_key.contains(code)) if is_code_like(code) else false()
    code_score = case((exact_code, EXACT_CODE), (partial_code, PARTIAL_CODE), else_=0)
    has_concept = [or_(*[has_word(word) for word in concept.words]) for concept in prepared.concepts]

    code_scores: dict[uuid.UUID, int] = {}
    concept_scores: dict[uuid.UUID, list[float]] = {}
    for part_id, part_code_score, *found in db.execute(
        select(Part.id, code_score, *has_concept).where(in_shop, or_(exact_code, partial_code, *has_concept))
    ):
        code_scores[part_id] = part_code_score
        concept_scores[part_id] = [1.0 if hit else 0.0 for hit in found]
    return code_scores, concept_scores


def _add_alike_words(db, in_shop, concepts, indexes, concept_scores, threshold) -> None:
    """Scores the given concepts by how alike the typed words are to the part's words."""
    if not indexes:
        return
    typed = [concepts[index].typed for index in indexes]
    rows = read_with_trigram_index(
        db,
        likely=or_(*[literal(word).op("<%")(Part.search_words) for word in typed]),
        scores=[func.word_similarity(word, Part.search_words) for word in typed],
        in_shop=in_shop,
        threshold=threshold,
    )
    for part_id, *similarities in rows:
        scores = concept_scores.setdefault(part_id, [0.0] * len(concepts))
        for index, similarity in zip(indexes, similarities):
            scores[index] = max(scores[index], similarity)


def _alike_codes(db, in_shop, code: str) -> dict[uuid.UUID, float]:
    """Part numbers close to what was typed ("bp003" is close to "bp001")."""
    if len(code) < 3:
        return {}
    alike = func.greatest(func.word_similarity(code, Part.sku_key), func.word_similarity(code, Part.oem_key))
    rows = read_with_trigram_index(
        db,
        likely=or_(literal(code).op("<%")(Part.sku_key), literal(code).op("<%")(Part.oem_key)),
        scores=[alike],
        in_shop=in_shop,
        threshold=CLOSEST_MATCH,
    )
    return dict(rows)


def read_with_trigram_index(db: Session, likely, scores: list, in_shop, threshold: float) -> list:
    """(part id, *scores) for the parts of this shop where `likely` (a trigram condition) is true.

    PostgreSQL thinks comparing words is cheap, so it would compare every part one by one
    (about 20 times slower). So the likely parts are found first with the trigram condition
    alone, in a separate step that can only use the trigram index, and only they are scored."""
    db.execute(text(f"SET LOCAL pg_trgm.word_similarity_threshold = {threshold}"))
    db.execute(text("SET LOCAL enable_seqscan = off"))
    try:
        found = select(Part.id).where(likely).cte("likely_parts").prefix_with("MATERIALIZED")
        return db.execute(select(Part.id, *scores).join(found, found.c.id == Part.id).where(in_shop)).all()
    finally:
        db.execute(text("SET LOCAL enable_seqscan = on"))


def _average(scores: list[float]) -> float:
    return sum(scores) / len(scores) if scores else 0.0


def _best_first(scores: dict[uuid.UUID, float]) -> list[tuple[uuid.UUID, float]]:
    return sorted(scores.items(), key=lambda match: match[1], reverse=True)


def as_table(matches: list[tuple[uuid.UUID, float]]) -> Subquery:
    """The matches as a small table (part_id, score) other queries can join."""
    ids = bindparam("matched_ids", [part_id for part_id, _ in matches], type_=ARRAY(Uuid))
    scores = bindparam("matched_scores", [score for _, score in matches], type_=ARRAY(Float))
    return select(func.unnest(ids).label("part_id"), func.unnest(scores).label("score")).subquery()
