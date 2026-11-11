"""How sure are we that the forecasts beat the baseline? 95% confidence intervals on the demo shop.

Run inside Docker (after app.demo.demo_shop):  docker compose exec api python -m app.demo.check_confidence
Method: paired bootstrap over part-branch pairs. Each resample draws pairs with replacement and
recomputes both WAPEs on the same pairs, so the gain keeps the link between the two forecasts.
These are scores on made-up data, not the accuracy a real shop will see.
"""

import numpy as np
from sqlalchemy import select

from app.db import SessionLocal
from app.demo.check_forecasts import true_future_totals
from app.demo.demo_shop import DEMO_SHOP_NAME
from app.demo.production_guard import refuse_demo_in_production
from app.forecast.engine import BASELINE, HORIZONS, forecast_all
from app.forecast.run import load_demand
from app.models import Organization

RESAMPLES = 2000
SEED = 7


def wape(forecast: np.ndarray, actual: np.ndarray) -> float:
    return float(np.abs(forecast - actual).sum() / actual.sum())


def paired_bootstrap(chosen: np.ndarray, baseline: np.ndarray, actual: np.ndarray,
                     resamples: int = RESAMPLES, seed: int = SEED) -> dict[str, tuple[float, float, float]]:
    """Point value and 95% interval of each WAPE and of the relative gain (1 - chosen/baseline)."""
    rng = np.random.default_rng(seed)
    n = len(actual)
    err_chosen, err_base = np.abs(chosen - actual), np.abs(baseline - actual)
    stats = {"chosen": [], "baseline": [], "gain": []}
    for _ in range(resamples):
        pick = rng.integers(0, n, n)
        sold = actual[pick].sum()
        if sold == 0:
            continue
        c, b = err_chosen[pick].sum() / sold, err_base[pick].sum() / sold
        stats["chosen"].append(c)
        stats["baseline"].append(b)
        stats["gain"].append(1 - c / b)
    point = {"chosen": wape(chosen, actual), "baseline": wape(baseline, actual)}
    point["gain"] = 1 - point["chosen"] / point["baseline"]
    return {k: (point[k], float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) for k, v in stats.items()}


def main() -> None:
    refuse_demo_in_production()
    with SessionLocal() as db:
        shop_id = db.scalar(select(Organization.id).where(Organization.is_demo, Organization.name == DEMO_SHOP_NAME))
        if shop_id is None:
            raise SystemExit("No demo shop. Run: python -m app.demo.demo_shop")
        shop = load_demand(db, shop_id)
        results = forecast_all(shop.demand, shop.first_day)
        truth = true_future_totals(db, shop)

    print(f"Paired bootstrap, {RESAMPLES} resamples of part-branch pairs, 95% intervals")
    for horizon in HORIZONS:
        mine = [r for r in results if r.horizon == horizon]
        actual = truth[horizon][[r.row for r in mine]]
        chosen = np.array([r.quantity for r in mine])
        baseline = np.array([r.every_method[BASELINE] for r in mine])
        s = paired_bootstrap(chosen, baseline, actual)
        print(f"{horizon} days ({len(mine)} pairs): "
              f"chosen {s['chosen'][0]:.3f} [{s['chosen'][1]:.3f}, {s['chosen'][2]:.3f}]  "
              f"baseline {s['baseline'][0]:.3f} [{s['baseline'][1]:.3f}, {s['baseline'][2]:.3f}]  "
              f"gain {100 * s['gain'][0]:.1f}% [{100 * s['gain'][1]:.1f}%, {100 * s['gain'][2]:.1f}%]")


if __name__ == "__main__":
    main()
