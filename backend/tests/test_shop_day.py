from datetime import UTC, date, datetime

from app import shop_day
from app.alerts import run as alerts_run
from app.shop_day import shop_today
from app.stock_outs import record_stock_outs_now
from tests.test_stock_outs import periods, shop_with_stock

# 00:30 on 16 June in Casablanca (UTC+1 then) is still 15 June in UTC. (Since 20 September 2026
# Morocco is on UTC+0, tzdata 2026c, so the two days only differ when that changes again.)
HALF_PAST_MIDNIGHT_IN_CASABLANCA = datetime(2026, 6, 15, 23, 30, tzinfo=UTC)
SHOP_DAY = date(2026, 6, 16)


class FrozenClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return HALF_PAST_MIDNIGHT_IN_CASABLANCA.astimezone(tz)


def test_half_past_midnight_in_casablanca_is_already_the_next_day():
    assert shop_today(HALF_PAST_MIDNIGHT_IN_CASABLANCA) == SHOP_DAY


def test_the_stock_out_recorder_saves_the_shops_day(monkeypatch):
    monkeypatch.setattr(shop_day, "datetime", FrozenClock)
    shop, parts = shop_with_stock("Real", {"EMPTY": 0})

    record_stock_outs_now(shop)

    assert periods(shop) == [(parts["EMPTY"], SHOP_DAY, SHOP_DAY)]


def test_the_daily_alerts_run_on_the_shops_day(monkeypatch):
    monkeypatch.setattr(shop_day, "datetime", FrozenClock)
    days = []
    monkeypatch.setattr(alerts_run, "run_alerts", lambda db, organization_id, today: days.append(today) or [])
    shop, _parts = shop_with_stock("Real", {"EMPTY": 0})

    alerts_run.run_alerts_now(shop)

    assert days == [SHOP_DAY]
