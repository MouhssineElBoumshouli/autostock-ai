"""Order suggestion math, budget cuts and the replay: pure functions, no database."""

import math

import numpy as np
import pytest

from app.ordering.budget import BudgetLine, apply_budget, expected_missed, line_value, missed_sales_prevented
from app.ordering.reasons import reason
from app.ordering.replay import Today, autostock_rule, minimum_rule, replay
from app.ordering.suggest import (
    HorizonForecast,
    Position,
    days_covered,
    expected_and_cushion,
    order_quantity,
    pick_horizon,
    round_up_to_pack,
    suggest,
    whole_need,
)

FORECASTS = (HorizonForecast(7, 7.0, 11.0), HorizonForecast(30, 30.0, 40.0), HorizonForecast(60, 60.0, 75.0))


def position(**changes) -> Position:
    values = dict(on_hand=6, on_order=0, pack_size=1, delivery_days=14, sold_last_28_days=30, sold_last_90_days=90, forecasts=FORECASTS)
    return Position(**{**values, **changes})


# --- need and cushion ---

def test_days_covered_is_delivery_plus_a_week_until_the_next_order():
    assert days_covered(14) == 21
    assert days_covered(0) == 7


def test_the_shortest_forecast_that_covers_the_days_is_used():
    assert pick_horizon(FORECASTS, 5).horizon == 7
    assert pick_horizon(FORECASTS, 21).horizon == 30
    assert pick_horizon(FORECASTS, 45).horizon == 60
    assert pick_horizon(FORECASTS, 90).horizon == 60  # nothing longer: the longest


def test_expected_sales_scale_with_days_and_the_cushion_with_their_square_root():
    expected, cushion = expected_and_cushion(FORECASTS, 21)
    assert expected == pytest.approx(21.0)  # 30 in 30 days -> 21 in 21 days
    assert cushion == pytest.approx(10 * math.sqrt(21 / 30))  # 90% cushion of 10 for 30 days


def test_a_forecast_with_no_room_above_gets_no_cushion():
    _, cushion = expected_and_cushion((HorizonForecast(30, 30.0, 30.0),), 21)
    assert cushion == 0


def test_need_is_rounded_up_to_whole_pieces_but_not_by_float_noise():
    assert whole_need(21.0, 8.37) == 30
    assert whole_need(2.0000000001, 1.0) == 3


# --- order quantity and packs ---

def test_pack_rounding_goes_up_to_whole_packs():
    assert round_up_to_pack(7, 5) == 10
    assert round_up_to_pack(10, 5) == 10
    assert round_up_to_pack(1, 10) == 10
    assert round_up_to_pack(3, 0) == 3  # a missing pack size counts as 1


def test_nothing_below_zero():
    assert round_up_to_pack(0, 5) == 0
    assert round_up_to_pack(-4, 5) == 0
    assert order_quantity(need=5, on_hand=10, on_order=0, pack_size=1) == 0


def test_order_is_need_minus_on_hand_minus_already_ordered():
    assert order_quantity(need=30, on_hand=6, on_order=10, pack_size=1) == 14
    assert order_quantity(need=30, on_hand=6, on_order=10, pack_size=5) == 15


def test_suggest_puts_it_together():
    s = suggest(position())
    assert s.rule == "forecast"
    assert s.days_covered == 21
    assert s.need == 30
    assert s.quantity == 24  # 30 needed, 6 on the shelf


def test_stock_already_ordered_lowers_the_order():
    assert suggest(position(on_order=20)).quantity == 4


# --- slow sellers ---

def test_no_recent_sales_and_stock_on_shelf_is_not_ordered():
    s = suggest(position(sold_last_28_days=0, on_hand=1, sold_last_90_days=3))
    assert (s.quantity, s.rule) == (0, "slow_skip")


def test_no_sale_in_90_days_is_not_ordered_even_when_out():
    s = suggest(position(sold_last_28_days=0, sold_last_90_days=0, on_hand=0))
    assert (s.quantity, s.rule) == (0, "slow_skip")


def test_out_of_stock_slow_seller_that_sold_lately_gets_at_least_one():
    tiny = (HorizonForecast(30, 0.2, 0.4),)
    s = suggest(position(sold_last_28_days=0, sold_last_90_days=2, on_hand=0, forecasts=tiny))
    assert (s.quantity, s.rule) == (1, "slow_out_of_stock")
    boxed = suggest(position(sold_last_28_days=0, sold_last_90_days=2, on_hand=0, forecasts=tiny, pack_size=4))
    assert boxed.quantity == 4


def test_a_part_without_forecasts_but_recent_sales_orders_nothing_by_guessing():
    assert suggest(position(forecasts=())).quantity == 0


# --- reasons ---

def test_reason_says_why_this_part_and_why_this_number():
    weekly_9 = (HorizonForecast(30, 9 * 30 / 7, 9 * 30 / 7 + 8),)
    s = suggest(position(forecasts=weekly_9))
    text = reason(s, 14, 6, 0, 1, 90)
    assert text.startswith("Sells about 9 a week, supplier takes 14 days, 6 left: order ")
    assert f"order {s.quantity} to cover the next 21 days" in text


def test_reason_mentions_packs_orders_on_the_way_and_slow_sellers():
    s = suggest(position(pack_size=5, on_order=3))
    assert "6 left, 3 already ordered" in reason(s, 14, 6, 3, 5, 90)
    assert "(packs of 5)" in reason(s, 14, 6, 3, 5, 90)
    slow = suggest(position(sold_last_28_days=0, sold_last_90_days=2, on_hand=0))
    assert reason(slow, 14, 0, 0, 1, 2).startswith("Out of stock, sold 2 in the last 90 days")


def test_slow_rates_are_said_per_month():
    s = suggest(position(forecasts=(HorizonForecast(30, 2.0, 4.0),)))
    assert reason(s, 14, 0, 0, 1, 6).startswith("Sells about 2 a month")


# --- budget ---

def test_expected_missed_sales_without_uncertainty_is_the_plain_shortfall():
    assert expected_missed(10, 0, 4) == 6
    assert expected_missed(10, 0, 12) == 0


def test_expected_missed_sales_with_uncertainty():
    assert expected_missed(0, 1, 0) == pytest.approx(1 / math.sqrt(2 * math.pi))  # standard normal: 0.399
    assert expected_missed(20, 5, 100) == pytest.approx(0, abs=1e-9)


def test_ordering_more_prevents_more_missed_sales_but_less_and_less():
    first = missed_sales_prevented(20, 5, 10, 5)
    second = missed_sales_prevented(20, 5, 15, 5)
    assert first > second > 0


def test_line_value_is_prevented_pieces_times_margin():
    assert line_value(2.0, unit_cost=700, sale_price=1000) == 600
    assert line_value(2.0, unit_cost=None, sale_price=1000) == 0
    assert line_value(2.0, unit_cost=1200, sale_price=1000) == 0  # sold at a loss: no margin to save


def test_no_budget_keeps_everything():
    lines = [BudgetLine("a", 500, 10), BudgetLine("b", 900, 1)]
    assert apply_budget(lines, None) == (lines, [])


def test_budget_keeps_the_best_value_per_dirham_first_and_cuts_the_rest():
    lines = [
        BudgetLine("big but weak", 6000, 600),  # 0.10 per dirham
        BudgetLine("strong", 3000, 900),  # 0.30
        BudgetLine("small", 1000, 200),  # 0.20
    ]
    kept, cut = apply_budget(lines, 4500)
    assert [line.key for line in kept] == ["strong", "small"]
    assert [line.key for line in cut] == ["big but weak"]


def test_a_smaller_line_after_a_cut_one_can_still_fit():
    lines = [BudgetLine("best", 3000, 900), BudgetLine("too big", 5000, 1000), BudgetLine("fits", 1000, 100)]
    kept, cut = apply_budget(lines, 4000)
    assert [line.key for line in kept] == ["best", "fits"]
    assert [line.key for line in cut] == ["too big"]


def test_free_lines_are_kept_first():
    kept, cut = apply_budget([BudgetLine("paid", 100, 50), BudgetLine("free", 0, 0)], 0)
    assert [line.key for line in kept] == ["free"]
    assert [line.key for line in cut] == ["paid"]


# --- replay ---

def no_orders(today: Today) -> None:
    return None


def test_replay_counts_lost_sales_empty_days_and_stock_value():
    demand = np.array([[1.0, 1.0, 1.0, 1.0]])
    result = replay(demand, np.zeros((1, 0)), np.array([2]), np.array([3]), no_orders, np.array([100.0]), np.array([150.0]))
    assert result.lost_pieces == 2
    assert result.days_out == 2
    assert result.lost_money == 300
    assert result.average_stock_value == pytest.approx((1 + 0 + 0 + 0) * 100 / 4)
    assert result.orders == 0


def test_a_customer_who_empties_the_shelf_is_not_a_day_out():
    result = replay(np.array([[2.0]]), np.zeros((1, 0)), np.array([2]), np.array([1]), no_orders, np.ones(1), np.ones(1))
    assert (result.days_out, result.lost_pieces) == (0, 0)


def test_orders_arrive_after_the_delivery_days():
    def order_on_day_0(today: Today):
        return np.array([5]) if today.day == 0 else None

    demand = np.array([[0.0, 0.0, 3.0, 3.0]])
    result = replay(demand, np.zeros((1, 0)), np.array([0]), np.array([2]), order_on_day_0, np.ones(1), np.ones(1))
    assert result.lost_pieces == 1  # 5 arrive on day 2: 3 sold, then 2 of 3 on day 3
    assert result.orders == 1


def test_the_rule_never_sees_true_demand_on_empty_days():
    seen_by_rule = []

    def watch(today: Today):
        seen_by_rule.append(today.seen.copy())
        return None

    demand = np.array([[1.0, 4.0, 2.0]])
    replay(demand, np.array([[3.0]]), np.array([3]), np.array([1]), watch, np.ones(1), np.ones(1))
    last = seen_by_rule[-1][0]
    assert last[0] == 3  # history from before the replay
    assert last[1] == 1
    assert np.isnan(last[2])  # wanted 4, had 2: that day's real demand is unknown to the shop


def test_minimum_rule_orders_back_up_to_twice_the_minimum_counting_orders_on_the_way():
    rule = minimum_rule(np.array([4, 4, 4]), np.array([1, 1, 5]))
    today = Today(0, np.array([1.0, 5.0, 1.0]), np.array([1.0, 0.0, 0.0]), np.zeros((3, 0)))
    assert list(rule(today)) == [6, 0, 10]  # 8 - 2; above the minimum; 7 rounded to packs of 5


def test_autostock_rule_orders_only_on_review_days_with_fresh_forecasts():
    calls = []

    def forecaster(seen):
        calls.append(seen.shape[1])
        return [FORECASTS]

    rule = autostock_rule(forecaster, np.array([1]), np.array([14]))
    seen = np.ones((1, 40))
    assert rule(Today(3, np.array([6.0]), np.array([0.0]), seen)) is None
    assert list(rule(Today(7, np.array([6.0]), np.array([0.0]), seen))) == [24]
    assert calls == [40]


def test_autostock_rule_applies_the_slow_seller_rule_from_what_it_saw():
    rule = autostock_rule(lambda seen: [FORECASTS], np.array([1]), np.array([14]))
    no_recent_sales = np.concatenate([np.ones((1, 60)), np.zeros((1, 30))], axis=1)
    assert list(rule(Today(0, np.array([2.0]), np.array([0.0]), no_recent_sales))) == [0]


def test_replay_with_autostock_beats_doing_nothing_on_steady_demand():
    days = 60
    demand = np.full((1, days), 2.0)
    past = np.full((1, 60), 2.0)
    steady = (HorizonForecast(7, 14.0, 18.0), HorizonForecast(30, 60.0, 70.0), HorizonForecast(60, 120.0, 135.0))
    rule = autostock_rule(lambda seen: [steady], np.array([1]), np.array([5]))
    ordered = replay(demand, past, np.array([10]), np.array([5]), rule, np.ones(1), np.ones(1))
    idle = replay(demand, past, np.array([10]), np.array([5]), no_orders, np.ones(1), np.ones(1))
    assert ordered.lost_pieces == 0
    assert idle.lost_pieces == 2 * days - 10
