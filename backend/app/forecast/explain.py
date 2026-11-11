"""How much a part's own forecast beat a simple 4-week average, as a plain percentage.
The website turns this into a sentence in the person's own language."""

from app.forecast.engine import BASELINE


def beat_baseline_pct(method: str, method_wape: float | None, baseline_wape: float | None) -> int | None:
    """None when there is nothing to show off: the method IS the baseline, or it did not
    score better on this part's own past."""
    if method == BASELINE or method_wape is None or baseline_wape is None or baseline_wape <= 0:
        return None
    pct = round(100 * (1 - method_wape / baseline_wape))
    return pct if pct > 0 else None
