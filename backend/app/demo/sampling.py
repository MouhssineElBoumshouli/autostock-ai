"""Picks about 1 in 3 part-branch rows for the slow replay scripts (check_orders, check_alerts),
keeping each demand type's (smooth/erratic/slow/lumpy/no_sales) share the same as the full catalog.
Only for those two scripts: the demo shop itself, and check_forecasts, use every part.
"""

import numpy as np

from app.forecast.demand_types import demand_type

SAMPLE_EVERY = 3
SAMPLE_SEED = 11


def sample_every_third(past_demand: np.ndarray, must_keep: np.ndarray | None = None) -> np.ndarray:
    """Row indices of the sample, sorted. `past_demand` is sales before the replay starts (one row
    per part-branch pair), so the sample never peeks at the days being replayed. `must_keep` (e.g.
    check_alerts' planted problems) are always included and count toward their type's share, so a
    kind with few planted problems still gets more random rows to reach about 1 in 3."""
    types = np.array([demand_type(row) for row in past_demand])
    rng = np.random.default_rng(SAMPLE_SEED)
    keep = set(must_keep.tolist()) if must_keep is not None else set()
    chosen = set(keep)
    for kind in np.unique(types):
        rows = np.flatnonzero(types == kind)
        target = max(1, round(len(rows) / SAMPLE_EVERY))
        rest = np.array([r for r in rows if r not in keep])
        rng.shuffle(rest)
        still_needed = max(0, target - sum(1 for r in rows if r in keep))
        chosen.update(rest[:still_needed].tolist())
    return np.sort(np.array(list(chosen), dtype=int))
