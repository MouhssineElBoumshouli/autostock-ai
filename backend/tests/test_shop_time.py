from tests.helpers import new_browser


def test_anyone_can_read_the_shops_utc_offset():
    response = new_browser().get("/api/shop-time")

    assert response.status_code == 200, response.text
    # Since 20 Sep 2026 Morocco is permanently UTC+0.
    assert response.json() == {"utc_offset_minutes": 0}
