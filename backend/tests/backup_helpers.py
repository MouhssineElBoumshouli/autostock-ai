"""A shop with a bit of everything, for the backup, restore and update tests."""

import os
import subprocess
from datetime import date

from app.db import SessionLocal
from app.demo.demo_shop import create_demo_shop
from tests.helpers import add_member, set_up_shop
from tests.test_purchase_orders import one_suggestion


def shop_with_everything(browser) -> None:
    """The demo shop (small) and a real shop: owner + 1 staff, parts, stock, sales, a purchase order."""
    with SessionLocal() as db:
        create_demo_shop(db, date(2026, 9, 30), parts_count=4, history_days=60)
        db.commit()
    set_up_shop(browser)
    add_member(browser, "staff@shop.ma", "staff")
    _, line = one_suggestion(browser, sku="OIL-1", per_week=9, on_hand=6)
    assert browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve"}).status_code == 200


def run_backup_script(*args: str, folder, **env: str) -> subprocess.CompletedProcess:
    from app.backups import SCRIPT, database_env

    return subprocess.run(["sh", str(SCRIPT), *args], env={**os.environ, **database_env(), "BACKUP_DIR": str(folder), **env},
                          capture_output=True, text=True)
