"""Offline ML research CLI; never sends, modifies or imports Odoo records."""
import argparse
import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from ml.forecast import Observation, forecast_daily


def evaluate(csv_path: Path, horizon: int) -> dict:
    grouped = defaultdict(list)
    with csv_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        required = {"sku", "date", "units"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Expected CSV headers: sku,date,units")
        for row in reader:
            grouped[row["sku"]].append(
                Observation(date.fromisoformat(row["date"]), float(row["units"]))
            )
    if not grouped:
        raise ValueError("Input must contain at least one record")
    return {sku: forecast_daily(rows, horizon=horizon).as_json()
            for sku, rows in sorted(grouped.items())}


def main():
    parser = argparse.ArgumentParser(description="Evaluate offline demand forecasts")
    parser.add_argument("csv", type=Path, help="CSV with sku,date,units columns")
    parser.add_argument("--days", type=int, default=30, choices=[7, 30, 60])
    parser.add_argument("--output", type=Path, default=Path("ml/output/forecast.json"))
    args = parser.parse_args()
    result = evaluate(args.csv, args.days)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Evaluated {len(result)} products. Report: {args.output}")
    for sku, details in result.items():
        print(f"  {sku}: {details['status']} / {details['selected_method']}")


if __name__ == "__main__":
    main()
