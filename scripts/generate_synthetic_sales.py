"""Create explicit SYNTHETIC demo sales; no Bounaim Auto records are used."""
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path


PARTS = {
    "BP-001": (12, 5), "OF-203": (9, 3), "SP-104": (7, 2),
    "AF-331": (8, 2), "BT-912": (4, 1), "BR-210": (3, 2),
}


def generate(path: Path):
    rng = random.Random(20261009)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["sku", "date", "units"])
        for sku, (base, weekend_boost) in PARTS.items():
            for index in range(210):
                day = date(2026, 1, 1) + timedelta(days=index)
                weekly = weekend_boost if day.weekday() in (5, 6) else 0
                trend = base * 0.003 * index
                seasonal = math.sin(index * 2 * math.pi / 60) * base * .20
                noisy = rng.gauss(0, max(1.0, base * .23))
                units = max(0, round(base + weekly + trend + seasonal + noisy))
                writer.writerow([sku, day.isoformat(), units])
    print(f"SYNTHETIC data generated at {path}")


if __name__ == "__main__":
    generate(Path("ml/output/synthetic_daily_sales.csv"))
