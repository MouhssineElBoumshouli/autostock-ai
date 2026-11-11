from app.imports.matching import evaluate_matchers, evaluate_on_blind_set, keyword_match, suggest_field


def test_keyword_rule_understands_french_english_and_arabic():
    assert keyword_match("Réf.", "parts") == "sku"
    assert keyword_match("SKU", "parts") == "sku"
    assert keyword_match("رمز القطعة", "parts") == "sku"
    assert keyword_match("Désignation", "parts") == "name"
    assert keyword_match("Stock mini", "parts") == "min_stock"
    assert keyword_match("Qté en stock", "parts") == "quantity"  # not confused with "stock mini"
    assert keyword_match("Réf OEM", "parts") == "oem_reference"  # not confused with plain "Réf."
    assert keyword_match("Prix d'achat", "parts") == "unit_cost"
    assert keyword_match("Prix de vente", "parts") == "sale_price"
    assert keyword_match("Fournisseur", "parts") == "supplier"
    assert keyword_match("Date de vente", "sales") == "date"
    assert keyword_match("Unit price", "sales") == "unit_price"


def test_keyword_rule_understands_equivalent_part_files():
    assert keyword_match("Our code", "equivalents") == "our_code"
    assert keyword_match("Cross reference", "equivalents") == "equivalent_code"
    assert keyword_match("Code", "equivalents") == "our_code"


def test_keyword_rule_ignores_columns_that_are_not_a_known_field():
    assert keyword_match("Notes", "parts") is None
    assert keyword_match("Image", "parts") is None
    assert keyword_match("Customer", "sales") is None


def test_short_keywords_only_match_whole_words():
    # A short keyword (4 letters or less) must not match inside a longer, unrelated word.
    assert keyword_match("Catalogue", "parts") is None  # not "cat" (category)
    assert keyword_match("Locataire", "parts") is None  # not "loc" (branch)
    assert keyword_match("Salesperson", "parts") is None  # not "sale" (sale price)
    # "code" alone means SKU, but as part of a longer header it almost never does.
    assert keyword_match("Code postal client", "parts") is None
    assert keyword_match("Code barre", "parts") is None
    assert keyword_match("Code", "parts") == "sku"


def test_keyword_rule_on_real_world_edge_cases():
    assert keyword_match("Stock alerte", "parts") == "min_stock"
    assert keyword_match("Dernière vente", "parts") is None  # a date, not a price
    assert keyword_match("Prix TTC", "parts") == "sale_price"
    assert keyword_match("Prix HT", "parts") == "sale_price"
    assert keyword_match("Prix achat HT", "parts") == "unit_cost"  # not confused with "Prix TTC"


def test_suggest_field_never_returns_a_field_outside_the_kind():
    for header in ["SKU", "Date", "Unit price", "Brand"]:
        field = suggest_field(header, "sales")
        assert field in {"date", "sku", "quantity", "unit_price", "branch", None}


def test_evaluate_matchers_scores_both_approaches_on_held_out_headers():
    scores = evaluate_matchers()

    assert set(scores) == {"parts", "sales"}
    for kind, result in scores.items():
        assert result["examples"] > 0
        assert 0.0 <= result["keyword_rule"] <= 1.0
        assert 0.0 <= result["scikit_learn"] <= 1.0
    # The keyword rule is the one actually used (see _USE_MODEL in matching.py) because it scored
    # better on headers shaped unlike anything either approach was given as training data.
    assert scores["parts"]["keyword_rule"] > scores["parts"]["scikit_learn"]
    assert scores["sales"]["keyword_rule"] > scores["sales"]["scikit_learn"]


def test_evaluate_on_blind_set_scores_both_approaches():
    # blind_test_headers.py was written before this fix and is never used to train or tune
    # either approach, so this is the most honest score either one gets.
    scores = evaluate_on_blind_set()

    assert set(scores) == {"parts", "sales"}
    for kind, result in scores.items():
        assert result["examples"] > 0
        assert 0.0 <= result["keyword_rule"] <= 1.0
        assert 0.0 <= result["scikit_learn"] <= 1.0
    assert scores["parts"]["keyword_rule"] > scores["parts"]["scikit_learn"]
    assert scores["sales"]["keyword_rule"] > scores["sales"]["scikit_learn"]


def test_pack_size_headers_are_recognised():
    assert keyword_match("Colisage", "parts") == "pack_size"
    assert keyword_match("Qty per pack", "parts") == "pack_size"
    assert keyword_match("Conditionnement", "parts") == "pack_size"
