"""Create explicit SYNTHETIC demo sales; no Bounaim Auto records are used."""
import csv
from pathlib import Path
import sys

# Direct script execution places `scripts/`, rather than the repository root,
# on `sys.path`. Keep the documented `python scripts/...` entry point usable.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from ml.synthetic import iter_synthetic_sales


def generate(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["sku", "date", "units"])
        for sku, day, units in iter_synthetic_sales():
            writer.writerow([sku, day.isoformat(), units])
    print(f"SYNTHETIC data generated at {path}")


if __name__ == "__main__":
    generate(REPO_ROOT / "ml/output/synthetic_daily_sales.csv")
