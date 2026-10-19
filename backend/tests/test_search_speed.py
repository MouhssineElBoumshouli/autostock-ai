"""Part search must answer in under 0.2 seconds with 10,000 parts.

The blind searches are run against the fixture shop plus 10,000 made-up parts named with the
same kind of words (filters, pads, belts, front/rear...), so every search has many look-alikes.
Run with -s to see the times:  pytest tests/test_search_speed.py -s
"""

import time

from sqlalchemy import text

from app.db import engine
from app.search.blind_test_searches import BLIND_SEARCHES
from tests.helpers import set_up_shop
from tests.import_helpers import import_parts
from tests.test_search_blind import score

LOOK_ALIKES = text("""
INSERT INTO parts (id, created_at, organization_id, sku, name, brand, category, oem_reference, min_stock, is_active)
SELECT gen_random_uuid(), now(), (SELECT id FROM organizations), 'GEN-' || n,
       (ARRAY['Filtre', 'Courroie', 'Pompe', 'Capteur', 'Joint', 'Durite', 'Silent bloc', 'Cable', 'Support',
              'Sensor', 'Gasket', 'Hose', 'Mount', 'Bulb', 'Relay', 'Switch'])[1 + n % 16]
       || ' ' || (ARRAY['avant', 'arrière', 'gauche', 'droit', 'front', 'rear', 'left', 'right', 'moteur', 'boîte'])[1 + n % 10]
       || ' ' || (ARRAY['Peugeot 208', 'Renault Clio', 'Dacia Logan', 'VW Golf', 'Fiat Punto', 'Toyota Yaris'])[1 + n % 6]
       || ' type ' || n % 97,
       (ARRAY['Bosch', 'Valeo', 'SKF', 'Gates', 'Febi', 'Corteco'])[1 + n % 6],
       (ARRAY['Moteur', 'Freinage', 'Suspension', 'Electrical', 'Cooling'])[1 + n % 5],
       lpad((n * 7919 % 9999991)::text, 10, '0'), 1, true
FROM generate_series(1, 10000) AS n
""")


def test_search_is_fast_with_ten_thousand_parts(browser):
    set_up_shop(browser)
    import_parts(browser)
    import_parts(browser, "parts_en_clean.csv")
    with engine.begin() as connection:
        connection.execute(LOOK_ALIKES)
        connection.execute(text("ANALYZE parts"))

    times = []

    def timed_search(search: str) -> list[str]:
        started = time.perf_counter()
        response = browser.get("/api/stock/parts", params={"search": search})
        times.append((time.perf_counter() - started, search))
        assert response.status_code == 200, response.text
        return [item["sku"] for item in response.json()["items"]]

    first, top_three, misses = score(timed_search)
    times.sort()
    median, (slowest, slowest_search) = times[len(times) // 2][0], times[-1]
    print(f"\n{len(times)} searches with 10,034 parts: median {median * 1000:.0f} ms, "
          f"slowest {slowest * 1000:.0f} ms ({slowest_search!r})")
    print(f"blind set among look-alikes: right part 1st {first:.0%}, in top 3 {top_three:.0%}")
    print("misses (1st place):\n  " + "\n  ".join(misses))

    assert slowest < 0.2
