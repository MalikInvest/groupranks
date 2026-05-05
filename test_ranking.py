"""Unit tests for the IBD-style RS formula and group ranking math."""
import numpy as np
import pandas as pd

from ranking import (
    weighted_rs_raw,
    rs_rating_1_99,
    least_squares_slope,
    RS_LOOKBACKS,
    RS_WEIGHTS,
    TRADING_DAYS_PER_YEAR,
)


def make_constant_path(value: float, n: int = 300) -> np.ndarray:
    return np.full(n, value, dtype=float)


def test_rs_formula_constant_path_equals_one():
    """A flat price path should give RS = 0.4 + 0.2 + 0.2 + 0.2 = 1.0 exactly."""
    n = 300
    df = pd.DataFrame({"FLAT": make_constant_path(50.0, n)})
    rs = weighted_rs_raw(df)
    assert abs(rs["FLAT"] - 1.0) < 1e-12, f"got {rs['FLAT']!r}"


def test_rs_formula_explicit_values():
    """Construct a path where the ratios at each lookback are known, then
    confirm the weighted sum matches by hand."""
    n = 300
    p = np.full(n, 100.0)
    # Set last to 200, and the 4 reference days to fixed values.
    p[-1] = 200.0
    p[-1 - 65] = 100.0   # ratio 2.0
    p[-1 - 130] = 80.0   # ratio 2.5
    p[-1 - 195] = 50.0   # ratio 4.0
    p[-1 - 260] = 40.0   # ratio 5.0
    expected = 0.4 * 2.0 + 0.2 * 2.5 + 0.2 * 4.0 + 0.2 * 5.0
    df = pd.DataFrame({"X": p})
    rs = weighted_rs_raw(df)
    assert abs(rs["X"] - expected) < 1e-12, f"got {rs['X']}, expected {expected}"


def test_rs_rating_bounds():
    """RS Rating must always lie in [1, 99] for a reasonable distribution."""
    rng = np.random.default_rng(0)
    raw = pd.Series(rng.normal(size=500))
    rating = rs_rating_1_99(raw)
    assert rating.min() >= 1
    assert rating.max() <= 99
    # spread should cover most of the range
    assert rating.max() - rating.min() > 90


def test_rs_rating_monotone():
    """Higher raw RS should never produce a lower rating than a lower raw RS."""
    raw = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    rating = rs_rating_1_99(raw)
    # ratings must be sorted in the same order
    assert list(rating) == sorted(rating)


def test_least_squares_slope_recovers_known_drift():
    """A pure exponential e^(rt) over T days should yield slope = r * 252/T_unit."""
    n = 252
    # We use day-index x; slope_per_day = r/252 to give annualised slope = r.
    annual = 0.30
    daily = annual / TRADING_DAYS_PER_YEAR
    path = 100 * np.exp(daily * np.arange(n))
    slope = least_squares_slope(path)
    assert abs(slope - annual) < 1e-9


def test_least_squares_slope_handles_short_input():
    """Very short / invalid inputs should return NaN, not raise."""
    assert np.isnan(least_squares_slope(np.array([1.0, 2.0])))
    assert np.isnan(least_squares_slope(np.array([1.0] * 20 + [-1.0])))  # negative
    assert np.isnan(least_squares_slope(np.array([1.0] * 20 + [0.0])))   # zero


def test_pipeline_assigns_ranks():
    """End-to-end: trending-up groups outrank trending-down groups."""
    from prices import fetch_prices_synthetic
    from ranking import rank_groups

    constituents = {
        "FAKE": {
            "RISER_GROUP": ["UP1", "UP2", "UP3"],
            "FALLER_GROUP": ["DN1", "DN2", "DN3"],
            "FLAT_GROUP": ["FL1", "FL2", "FL3"],
        }
    }
    prices = fetch_prices_synthetic(
        ["UP1", "UP2", "UP3", "DN1", "DN2", "DN3", "FL1", "FL2", "FL3"]
    )
    # Override with deterministic linear paths so the test is hermetic.
    n = len(prices)
    base = np.arange(n, dtype=float)
    prices["UP1"] = 100 * np.exp(0.0010 * base)
    prices["UP2"] = 100 * np.exp(0.0011 * base)
    prices["UP3"] = 100 * np.exp(0.0012 * base)
    prices["DN1"] = 100 * np.exp(-0.0010 * base)
    prices["DN2"] = 100 * np.exp(-0.0011 * base)
    prices["DN3"] = 100 * np.exp(-0.0012 * base)
    prices["FL1"] = 100.0
    prices["FL2"] = 100.0
    prices["FL3"] = 100.0

    df = rank_groups(constituents, prices)
    ranks = df.set_index("group")["rank"]
    assert ranks["RISER_GROUP"] < ranks["FLAT_GROUP"] < ranks["FALLER_GROUP"]


if __name__ == "__main__":
    fns = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\nAll {len(fns)} tests passed.")
