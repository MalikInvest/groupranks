 """
Core IBD Industry Group Rank model.

Methodology (mirrors IBD/William O'Neil + Co. publicly described approach):

1. Per-stock 6-month weighted Relative Strength (RS):
       RS = 0.4 * (P / P_-65)
          + 0.2 * (P / P_-130)
          + 0.2 * (P / P_-195)
          + 0.2 * (P / P_-260)
   where P_-N is the close N trading days ago. Each stock is then converted
   to a 1-99 RS Rating by percentile rank against the full universe.

2. Per-group score: IBD describes their group score as a least-squares curve
   fit on the SUMMED prices of constituents. We replicate this by fitting a
   linear regression of log(sum_of_constituent_prices) on time over the last
   6 months and using the slope (annualised) as the price-trend score. We
   then blend this with the median RS Rating of the group's constituents to
   get a robust composite score that mirrors IBD's blended weightings.

3. Groups are sorted by composite score (descending) and assigned ranks 1..N.

The model is taxonomy-agnostic: pass any {group: [tickers]} mapping and it
ranks them all.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

# Trading-day lookbacks IBD uses for the 6-month weighted RS formula.
# Source: William O'Neil + Co. methodology references.
RS_LOOKBACKS = (65, 130, 195, 260)
RS_WEIGHTS = (0.4, 0.2, 0.2, 0.2)
SIX_MONTH_DAYS = 130   # roughly 6 calendar months of trading
TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------------
# Per-stock RS
# ---------------------------------------------------------------------------

def weighted_rs_raw(prices: pd.DataFrame) -> pd.Series:
    """Compute IBD-style 6-month weighted RS for each ticker (column).

    `prices` is a wide DataFrame indexed by date with a column per ticker.
    Returns a Series indexed by ticker. NaN for tickers without enough history.
    """
    if len(prices) < max(RS_LOOKBACKS) + 1:
        # Not enough history — return NaN for everyone but don't crash.
        return pd.Series(np.nan, index=prices.columns)

    last = prices.iloc[-1]
    parts = []
    for lookback, weight in zip(RS_LOOKBACKS, RS_WEIGHTS):
        ref = prices.iloc[-1 - lookback]
        # ratio with safe divide
        ratio = last / ref.replace(0, np.nan)
        parts.append(weight * ratio)
    return sum(parts)


def rs_rating_1_99(rs_raw: pd.Series) -> pd.Series:
    """Convert raw RS into 1..99 percentile rank against the full universe.

    Mirrors IBD's published RS Rating: 99 = top 1%, 1 = bottom 1%.
    """
    valid = rs_raw.dropna()
    if valid.empty:
        return pd.Series(np.nan, index=rs_raw.index)
    # rank ascending so highest RS gets rank == n, then map to 1..99
    ranks = valid.rank(method="average", ascending=True)
    pct = (ranks - 1) / max(len(valid) - 1, 1)  # 0..1
    rating = (pct * 98 + 1).round().astype(int)  # 1..99
    out = pd.Series(np.nan, index=rs_raw.index)
    out.loc[rating.index] = rating
    return out


# ---------------------------------------------------------------------------
# Per-group score
# ---------------------------------------------------------------------------

def least_squares_slope(values: np.ndarray) -> float:
    """Annualised slope of a linear fit to log(values) vs time.

    Returns slope in units of "log price per year" — equivalent to the
    constant continuously-compounded growth rate that best fits the path.
    """
    values = np.asarray(values, dtype=float)
    if values.size < 10 or not np.all(np.isfinite(values)) or np.any(values <= 0):
        return np.nan
    y = np.log(values)
    x = np.arange(len(y), dtype=float)
    # closed-form OLS slope
    x_mean = x.mean()
    y_mean = y.mean()
    num = ((x - x_mean) * (y - y_mean)).sum()
    den = ((x - x_mean) ** 2).sum()
    if den == 0:
        return np.nan
    slope_per_day = num / den
    return slope_per_day * TRADING_DAYS_PER_YEAR


@dataclass
class GroupScore:
    group: str
    sector: str
    n_stocks: int
    n_with_data: int
    median_rs_rating: float
    price_trend_annualised: float  # slope from least-squares fit
    composite_score: float


def score_group(
    group: str,
    sector: str,
    tickers: Sequence[str],
    prices: pd.DataFrame,
    rs_ratings: pd.Series,
    six_month_window: int = SIX_MONTH_DAYS,
    rs_weight: float = 0.6,
    trend_weight: float = 0.4,
) -> GroupScore:
    """Score a single industry group.

    Composite = rs_weight * normalised_median_RS + trend_weight * normalised_trend.
    Both inputs are normalised to z-scores at the universe level later.
    Here we just produce the raw inputs.
    """
    have = [t for t in tickers if t in prices.columns]
    if not have:
        return GroupScore(group, sector, len(tickers), 0, np.nan, np.nan, np.nan)

    sub = prices[have].iloc[-six_month_window:]
    # Sum constituent prices (IBD's "summed prices" approach).
    summed = sub.sum(axis=1, min_count=1).dropna()
    trend = least_squares_slope(summed.values) if len(summed) >= 10 else np.nan

    median_rs = rs_ratings.reindex(have).dropna().median()

    # composite computed at the universe level once all groups are scored
    return GroupScore(
        group=group,
        sector=sector,
        n_stocks=len(tickers),
        n_with_data=len(have),
        median_rs_rating=float(median_rs) if pd.notna(median_rs) else np.nan,
        price_trend_annualised=float(trend) if pd.notna(trend) else np.nan,
        composite_score=np.nan,
    )


# ---------------------------------------------------------------------------
# Universe-level: assemble ranks
# ---------------------------------------------------------------------------

def _zscore(s: pd.Series) -> pd.Series:
    valid = s.dropna()
    if valid.empty or valid.std(ddof=0) == 0:
        return pd.Series(0.0, index=s.index)
    z = (s - valid.mean()) / valid.std(ddof=0)
    return z.fillna(0.0)


def build_stock_table(
    constituents: Mapping[str, Mapping[str, Sequence[str]]],
    prices: pd.DataFrame,
    history_days: int = 130,
    fundamentals: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Per-stock detail: ticker, sector, group, RS rating (1..99), price,
    6-month price change, Shariah status (with optional debt-ratio refinement),
    and a compact price history string for inline charts.

    `fundamentals` is an optional DataFrame indexed by ticker with column
    `debt_to_market_cap`. If provided, Shariah classification will downgrade
    HALAL business-activity verdicts to QUESTIONABLE when ratio > 33%.
    """
    from shariah import classify_ticker  # local import to avoid hard dependency

    rs_raw = weighted_rs_raw(prices)
    rs_ratings = rs_rating_1_99(rs_raw)

    last_close = prices.iloc[-1]
    six_mo_ago_idx = -min(SIX_MONTH_DAYS + 1, len(prices))
    six_mo_close = prices.iloc[six_mo_ago_idx]
    six_mo_change = (last_close / six_mo_close) - 1.0

    # Compact history: roughly every-other-day closes per ticker (~65 points)
    # so charts stay smooth but the page stays under 1 MB. Rounded to 2dp,
    # ";"-separated. Used by the HTML to draw inline SVG charts with zero
    # external dependencies (works offline, on mobile, from file://).
    n_keep = min(history_days, len(prices))
    history_window = prices.iloc[-n_keep:]
    # Downsample by 2 — keeps recent end-points intact (last row always kept).
    keep_idx = list(range(len(history_window) - 1, -1, -2))[::-1]
    history_window = history_window.iloc[keep_idx]
    history_str = {
        col: ";".join(
            "" if pd.isna(v) else f"{v:.2f}"
            for v in history_window[col].values
        )
        for col in history_window.columns
    }

    # Build {ticker: debt_to_mcap} lookup if fundamentals were provided
    debt_lookup: dict[str, float] = {}
    if fundamentals is not None and "debt_to_market_cap" in fundamentals.columns:
        for tk, row in fundamentals.iterrows():
            r = row.get("debt_to_market_cap")
            if pd.notna(r):
                debt_lookup[tk] = float(r)

    rows = []
    for sector, groups in constituents.items():
        for group, tickers in groups.items():
            for t in tickers:
                debt_ratio = debt_lookup.get(t)
                shariah = classify_ticker(t, sector, group, debt_ratio)
                if t not in prices.columns:
                    rows.append({
                        "ticker": t, "sector": sector, "group": group,
                        "rs_rating": pd.NA, "last_close": pd.NA,
                        "six_month_change": pd.NA, "history": "",
                        "shariah_status": shariah.status,
                        "shariah_reason": shariah.reason,
                        "debt_to_market_cap": debt_ratio if debt_ratio is not None else pd.NA,
                    })
                    continue
                rows.append({
                    "ticker": t,
                    "sector": sector,
                    "group": group,
                    "rs_rating": rs_ratings.get(t, pd.NA),
                    "last_close": float(last_close.get(t, float("nan"))),
                    "six_month_change": float(six_mo_change.get(t, float("nan"))),
                    "history": history_str.get(t, ""),
                    "shariah_status": shariah.status,
                    "shariah_reason": shariah.reason,
                    "debt_to_market_cap": debt_ratio if debt_ratio is not None else pd.NA,
                })
    df = pd.DataFrame(rows)
    df["rs_rating"] = df["rs_rating"].astype("Int64")
    return df


def rank_groups(
    constituents: Mapping[str, Mapping[str, Sequence[str]]],
    prices: pd.DataFrame,
    rs_weight: float = 0.6,
    trend_weight: float = 0.4,
    fundamentals: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """End-to-end: given {sector: {group: [tickers]}} and a price panel,
    return a DataFrame with one row per group, ranked 1..N.

    Columns: group, sector, n_stocks, n_with_data, median_rs_rating,
             price_trend_annualised, composite_score, rank, pct_halal,
             n_halal, n_questionable, n_haram

    `fundamentals` is an optional DataFrame indexed by ticker with column
    `debt_to_market_cap`, used to refine Shariah counts.
    """
    from shariah import group_summary  # local import

    # Build {ticker: debt_to_mcap} lookup if fundamentals were provided
    debt_lookup: dict[str, float] = {}
    if fundamentals is not None and "debt_to_market_cap" in fundamentals.columns:
        for tk, row in fundamentals.iterrows():
            r = row.get("debt_to_market_cap")
            if pd.notna(r):
                debt_lookup[tk] = float(r)

    # 1. Per-stock RS rating across the full universe
    rs_raw = weighted_rs_raw(prices)
    rs_ratings = rs_rating_1_99(rs_raw)

    # 2. Per-group raw scores
    rows: list[GroupScore] = []
    for sector, groups in constituents.items():
        for group, tickers in groups.items():
            rows.append(score_group(group, sector, tickers, prices, rs_ratings))

    df = pd.DataFrame([r.__dict__ for r in rows])

    # 3. Combine median RS and trend into one composite via z-scores.
    z_rs = _zscore(df["median_rs_rating"])
    z_trend = _zscore(df["price_trend_annualised"])
    df["composite_score"] = rs_weight * z_rs + trend_weight * z_trend
    df.loc[df["n_with_data"] == 0, "composite_score"] = np.nan

    # 4. Rank: 1 = best (highest composite). NaNs go to the end.
    df["rank"] = df["composite_score"].rank(method="min", ascending=False).astype("Int64")

    # 5. Attach Shariah-coverage stats per group, using debt_lookup for
    # ratio-based refinement of HALAL business-activity verdicts.
    sh_summary = group_summary(constituents, debt_lookup)
    df["pct_halal"] = df["group"].map(
        lambda g: sh_summary.get(g, {}).get("pct_halal", np.nan)
    )
    df["n_halal"] = df["group"].map(
        lambda g: sh_summary.get(g, {}).get("halal", 0)
    )
    df["n_questionable"] = df["group"].map(
        lambda g: sh_summary.get(g, {}).get("questionable", 0)
    )
    df["n_haram"] = df["group"].map(
        lambda g: sh_summary.get(g, {}).get("haram", 0)
    )

    df = df.sort_values(["rank", "group"], na_position="last").reset_index(drop=True)
    return df
