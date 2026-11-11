"""Tells the website what time it is at the shop right now, as a plain offset from UTC.

Morocco moved to permanent UTC+0 on 20 Sep 2026. A browser or shop PC that still has old time
zone data would show every time an hour ahead if the website asked it to work out "Africa/
Casablanca" itself (Intl.DateTimeFormat), so instead every page that shows a time asks here and
shifts by this number -- trusting this container's own, up-to-date tzdata package, not whichever
computer happens to be looking (frontend/src/lib/format.ts).
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.shop_day import shop_utc_offset_minutes

router = APIRouter(prefix="/api/shop-time")


class ShopTimeOut(BaseModel):
    utc_offset_minutes: int


@router.get("")
def read_shop_time() -> ShopTimeOut:
    return ShopTimeOut(utc_offset_minutes=shop_utc_offset_minutes())
