"""Scores part search on the blind set (app/search/blind_test_searches.py), next to the plain
search the Stock screen used before (text contained in name, SKU or OEM reference, sorted by name).

Run with -s to see the scores:  pytest tests/test_search_blind.py -s
"""

from sqlalchemy import or_, select

from app.db import SessionLocal
from app.models import Part
from app.search.blind_test_searches import BLIND_SEARCHES
from tests.helpers import set_up_shop
from tests.import_helpers import import_parts


def plain_search(search: str) -> list[str]:
    term = f"%{search.strip()}%"
    with SessionLocal() as db:
        return list(db.scalars(
            select(Part.sku)
            .where(or_(Part.name.ilike(term), Part.sku.ilike(term), Part.oem_reference.ilike(term)))
            .order_by(Part.name, Part.sku)
        ))


def score(find) -> tuple[float, float, list[str]]:
    first = top_three = 0
    misses = []
    for search, right in BLIND_SEARCHES:
        found = find(search)
        first += bool(found[:1]) and found[0] in right
        top_three += any(sku in right for sku in found[:3])
        if not found[:1] or found[0] not in right:
            misses.append(f"{search!r} -> {found[:3]} (wanted {'/'.join(right)})")
    return first / len(BLIND_SEARCHES), top_three / len(BLIND_SEARCHES), misses


def test_new_search_beats_plain_search_on_the_blind_set(browser):
    set_up_shop(browser)
    import_parts(browser)
    import_parts(browser, "parts_en_clean.csv")

    def new_search(search: str) -> list[str]:
        response = browser.get("/api/stock/parts", params={"search": search})
        assert response.status_code == 200, response.text
        return [item["sku"] for item in response.json()["items"]]

    plain_first, plain_three, _ = score(plain_search)
    new_first, new_three, misses = score(new_search)
    print(f"\n{len(BLIND_SEARCHES)} blind searches")
    print(f"plain search: right part 1st {plain_first:.0%}, in top 3 {plain_three:.0%}")
    print(f"new search:   right part 1st {new_first:.0%}, in top 3 {new_three:.0%}")
    print("new search misses (1st place):\n  " + "\n  ".join(misses))

    assert new_first > plain_first
    assert new_three > plain_three
