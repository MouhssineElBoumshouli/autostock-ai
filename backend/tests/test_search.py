from sqlalchemy import func, select

from app.db import SessionLocal
from app.search.part_search import concepts_of
from tests.helpers import (
    OWNER_PASSWORD,
    add_member,
    audit_rows,
    create_other_shop,
    logged_in_browser,
    member_with_own_password,
    set_up_shop,
)
from tests.import_helpers import import_parts


def normalized(value: str) -> str:
    with SessionLocal() as db:
        return db.scalar(select(func.search_text(value)))


def code_key(value: str) -> str:
    with SessionLocal() as db:
        return db.scalar(select(func.search_code(value)))


def found(browser, search: str) -> list[str]:
    response = browser.get("/api/stock/parts", params={"search": search})
    assert response.status_code == 200, response.text
    return [item["sku"] for item in response.json()["items"]]


def shop_with_parts(browser):
    set_up_shop(browser)
    import_parts(browser)
    import_parts(browser, "parts_en_clean.csv")


# Normalizing


def test_text_is_lowercase_without_accents_or_punctuation():
    assert normalized("  Plaquettes de FREIN arrière ") == "plaquettes de frein arriere"
    assert normalized("Bougie d'allumage (kit)") == "bougie d allumage kit"
    assert normalized("W 712/95") == "w 712 95"


def test_arabic_letter_variants_and_diacritics_are_made_the_same():
    assert normalized("فِلْتَر") == normalized("فلتر")
    assert normalized("مضخة") == normalized("مضخه")
    assert normalized("أ إ آ") == "ا ا ا"
    assert normalized("مستشفى") == normalized("مستشفي")
    assert normalized("فلتـــر") == normalized("فلتر")  # stretched letters (tatweel)


def test_arabic_al_is_dropped_from_the_start_of_words():
    assert normalized("الفرامل الخلفية") == normalized("فرامل خلفية")


def test_part_numbers_ignore_spaces_dashes_dots_and_case():
    assert code_key("0 986 494 525") == code_key("0986494525") == "0986494525"
    assert code_key("BP-001") == code_key("bp001") == code_key("Bp.0 01") == "bp001"
    assert code_key("W 712/95") == "w71295"


def test_synonym_phrases_become_one_concept():
    groups = [["brake pads", "plaquettes de frein"], ["rear", "arriere"]]

    concepts = concepts_of("rear brake pads".split(), groups)

    assert [(concept.typed, concept.words) for concept in concepts] == [
        ("rear", ["rear", "arriere"]),
        ("brake pads", ["brake pads", "plaquettes de frein"]),
    ]


def test_little_words_are_dropped_unless_nothing_else_is_left():
    assert [c.typed for c in concepts_of("filtre a huile".split(), [])] == ["filtre", "huile"]
    assert [c.typed for c in concepts_of(["de"], [])] == ["de"]


# Search


def test_exact_part_number_comes_first_however_it_is_typed(browser):
    shop_with_parts(browser)

    assert found(browser, "bp001")[0] == "BP-001"
    assert found(browser, "0 986 494 525")[0] == "BP-001"
    assert found(browser, "w-712-95")[0] == "FL-200"
    assert found(browser, "BP-002")[0] == "BP-002"


def test_exact_part_number_beats_a_part_that_only_contains_it(browser):
    shop_with_parts(browser)

    # "0986494525" (BP-001) is exact; "09864945" is contained in both BP-001 and BP-002.
    assert found(browser, "0986494526")[0] == "BP-002"
    assert sorted(found(browser, "09864945")[:2]) == ["BP-001", "BP-002"]


def test_typos_and_partial_words_still_find_the_part(browser):
    shop_with_parts(browser)

    assert found(browser, "termostat")[0] == "TH-610"
    assert found(browser, "altenator")[0] == "AL-510"
    assert set(found(browser, "amort")[:2]) == {"AM-300", "AM-301"}


def test_synonyms_find_the_same_part_in_three_languages(browser):
    shop_with_parts(browser)

    assert found(browser, "plaquettes de frein arrière")[0] == "BP-002"
    assert found(browser, "rear brake pads")[0] == "BP-002"
    assert found(browser, "فحمات الفرامل الخلفية")[0] == "BP-002"


def test_a_part_matching_every_word_comes_before_one_matching_some(browser):
    shop_with_parts(browser)

    assert found(browser, "amortisseur avant droit")[:2] == ["AM-301", "AM-300"]


def test_nothing_found_gives_an_empty_list(browser):
    shop_with_parts(browser)

    assert found(browser, "zzzzqqq") == []
    assert found(browser, "%%%") == []


def test_picking_a_column_still_sorts_search_results_by_it(browser):
    shop_with_parts(browser)

    response = browser.get("/api/stock/parts", params={"search": "amortisseur", "sort": "sku", "direction": "desc"})

    assert [item["sku"] for item in response.json()["items"]] == ["AM-301", "AM-300"]


def test_search_never_shows_another_shops_parts(browser):
    shop_with_parts(browser)
    other_owner = create_other_shop()
    other = logged_in_browser(other_owner.email, OWNER_PASSWORD)

    assert found(other, "BP-001") == []
    assert found(other, "brake pads") == []


def test_search_uses_only_this_shops_synonyms(browser):
    shop_with_parts(browser)
    other_owner = create_other_shop()  # made without the default list
    other = logged_in_browser(other_owner.email, OWNER_PASSWORD)
    assert other.put("/api/synonyms", json={"groups": [["frigo", "liquide de refroidissement"]]}).status_code == 200

    assert found(browser, "frigo") == []


# Editing the synonym list


def test_new_shop_starts_with_the_default_list(browser):
    set_up_shop(browser)

    groups = browser.get("/api/synonyms").json()["groups"]

    assert ["brake pads" in group and "plaquettes de frein" in group for group in groups].count(True) == 1


def test_owner_edits_the_list_and_search_uses_it(browser):
    shop_with_parts(browser)
    assert found(browser, "frigo") == []

    response = browser.put("/api/synonyms", json={"groups": [["frigo", " liquide de refroidissement "], ["", "  "]]})

    assert response.status_code == 200, response.text
    assert response.json() == {"groups": [["frigo", "liquide de refroidissement"]]}
    assert found(browser, "frigo")[0] == "HL-901"
    change = audit_rows("synonyms.updated")[-1]
    assert change.after == {"groups": [["frigo", "liquide de refroidissement"]]}
    assert len(change.before["groups"]) > 10


def test_saving_the_same_list_writes_no_audit_row(browser):
    set_up_shop(browser)
    groups = browser.get("/api/synonyms").json()["groups"]

    browser.put("/api/synonyms", json={"groups": groups})

    assert audit_rows("synonyms.updated") == []


def test_groups_need_two_words(browser):
    set_up_shop(browser)

    response = browser.put("/api/synonyms", json={"groups": [["frein"], ["huile", "HUILE"]]})

    assert response.status_code == 422
    assert "two words" in response.json()["detail"]


def test_only_owners_can_see_or_edit_the_list(browser):
    set_up_shop(browser)
    add_member(browser, "manager@shop.ma", "manager")
    manager = member_with_own_password("manager@shop.ma")

    assert manager.get("/api/synonyms").status_code == 403
    assert manager.put("/api/synonyms", json={"groups": []}).status_code == 403


# Review examples: typos reach the word list, word-list matches count fully, closest guesses


def test_typos_reach_the_word_list():
    groups = [["plaquettes de frein", "brake pads"], ["demarreur", "starter"]]

    pads = concepts_of(["plaquete", "frein"], groups)
    starter = concepts_of(["demareur"], groups)

    assert len(pads) == 1 and "brake pads" in pads[0].words
    assert "starter" in starter[0].words


def test_a_word_starting_a_phrase_brings_its_group():
    concepts = concepts_of(["plaquettes", "avant"], [["plaquettes de frein", "brake pads"], ["avant", "front"]])

    assert [concept.words for concept in concepts] == [
        ["plaquettes", "plaquettes de frein", "brake pads"],
        ["avant", "front"],
    ]


def test_typo_finds_parts_named_in_both_languages(browser):
    shop_with_parts(browser)

    assert set(found(browser, "plaquete frein")[:2]) == {"BP-001", "BP-002"}  # Front brake pads, Plaquettes … arrière
    assert found(browser, "demareur")[0] == "ST-500"  # Starter motor


def test_word_list_match_counts_as_much_as_a_literal_match(browser):
    shop_with_parts(browser)

    assert found(browser, "plaquettes avant")[0] == "BP-001"  # Front brake pads, not the front shock absorbers


def test_closest_parts_are_shown_when_nothing_matches_well(browser):
    shop_with_parts(browser)

    words = browser.get("/api/stock/parts", params={"search": "courroie scooter velo"}).json()
    code = browser.get("/api/stock/parts", params={"search": "bp009"}).json()

    assert words["closest"] is True
    assert {"CR-450", "CR-451"} <= {item["sku"] for item in words["items"]}
    assert code["closest"] is True
    assert {"BP-001", "BP-002"} <= {item["sku"] for item in code["items"]}


def test_good_matches_are_not_marked_as_closest(browser):
    shop_with_parts(browser)

    response = browser.get("/api/stock/parts", params={"search": "courroie"}).json()

    assert response["closest"] is False


def test_no_closest_parts_when_nothing_is_similar(browser):
    shop_with_parts(browser)

    response = browser.get("/api/stock/parts", params={"search": "zzzzqqq"}).json()

    assert (response["items"], response["closest"]) == ([], False)


def test_default_word_list_covers_review_words(browser):
    shop_with_parts(browser)

    assert set(found(browser, "roulement")[:2]) == {"WB-410", "WB-411"}
    assert set(found(browser, "wheel bearing")[:2]) == {"WB-410", "WB-411"}
    assert found(browser, "démarreur")[0] == "ST-500"
    assert found(browser, "starter")[0] == "ST-500"
    for word in ("dynamo", "dinamo", "alternateur", "alternator"):
        assert found(browser, word)[0] == "AL-510", word
    for word in ("antigel", "liquide de refroidissement", "coolant"):
        assert found(browser, word)[0] == "HL-901", word
    assert found(browser, "bougie d'allumage")[0] == "SP-104"  # Spark plug iridium
    assert found(browser, "bougie de préchauffage")[0] == "SP-105"  # glow plug
