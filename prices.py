"""
Price data fetcher.

Two backends:
  - 'yfinance' — live data, requires internet + the `yfinance` package.
  - 'synthetic' — deterministic fake data for testing the pipeline offline.

The output is always a wide DataFrame: index = trading day, columns = tickers,
values = adjusted close.
"""
from __future__ import annotations

from typing import Iterable, Sequence
import numpy as np
import pandas as pd


def fetch_prices_yfinance(
    tickers: Sequence[str],
    period: str = "18mo",
    interval: str = "1d",
) -> pd.DataFrame:
    """Pull adjusted close prices from Yahoo Finance.

    Requires `yfinance` (pip install yfinance). 18mo gives a comfortable
    buffer over the 260-trading-day max lookback used for RS.
    """
    import yfinance as yf  # lazy import

    tickers = list(tickers)
    # Batch download — yfinance handles up to a few hundred at a time well.
    data = yf.download(
        tickers,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    if data is None or len(data) == 0:
        return pd.DataFrame()

    if len(tickers) == 1:
        # single-ticker shape is different
        prices = data[["Close"]].rename(columns={"Close": tickers[0]})
    else:
        # multi-ticker: data has a MultiIndex column (ticker, field).
        # Pull the Close field for each.
        try:
            prices = data.xs("Close", axis=1, level=1)
        except KeyError:
            # fallback for older yfinance versions
            prices = pd.DataFrame(
                {t: data[t]["Close"] for t in tickers if t in data.columns.levels[0]}
            )

    return prices.dropna(axis=1, how="all").sort_index()


def fetch_prices_synthetic(
    tickers: Sequence[str],
    n_days: int = 400,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate deterministic synthetic price paths for testing.

    Each ticker gets a geometric-Brownian-motion path with a per-ticker drift
    drawn deterministically from `seed + hash(ticker)`. This lets us validate
    the ranking pipeline without internet access.
    """
    rng_master = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n_days)
    out = {}
    for t in tickers:
        # per-ticker deterministic stream
        local_seed = (seed + abs(hash(t))) % (2**32)
        rng = np.random.default_rng(local_seed)
        # drift in [-0.4, +0.6] annualised — wide spread so ranks differentiate
        annual_drift = rng.uniform(-0.4, 0.6)
        annual_vol = rng.uniform(0.2, 0.6)
        dt = 1 / 252
        shocks = rng.normal(
            loc=(annual_drift - 0.5 * annual_vol**2) * dt,
            scale=annual_vol * np.sqrt(dt),
            size=n_days,
        )
        path = 100 * np.exp(np.cumsum(shocks))
        out[t] = path
    df = pd.DataFrame(out, index=dates)
    return df


def fetch_fundamentals_yfinance(
    tickers: Sequence[str],
    batch_size: int = 50,
) -> pd.DataFrame:
    """Pull total debt and market cap from Yahoo Finance for each ticker.

    Returns a DataFrame indexed by ticker with columns:
        market_cap          — float, USD
        total_debt          — float, USD (short-term + long-term, when available)
        debt_to_market_cap  — float, ratio (None if either input missing)
        ratio_source        — "info" | "balance_sheet" | "missing"

    yfinance's data quality is uneven. Some tickers return everything via
    Ticker.info (fast); others have nothing in info but have a balance_sheet.
    We try both and record which source we used so the page can be honest
    about reliability.
    """
    import yfinance as yf

    rows = []
    for t in tickers:
        try:
            yf_ticker = yf.Ticker(t)
            info = yf_ticker.info or {}
            mcap = info.get("marketCap")
            debt = info.get("totalDebt")
            source = "info"

            # Fallback: try the balance sheet if info didn't have it
            if (debt is None or debt == 0) or (mcap is None or mcap == 0):
                try:
                    bs = yf_ticker.balance_sheet
                    if bs is not None and not bs.empty:
                        most_recent = bs.iloc[:, 0]
                        st_debt = most_recent.get("Short Long Term Debt", 0) or 0
                        lt_debt = most_recent.get("Long Term Debt", 0) or 0
                        bs_debt = float(st_debt) + float(lt_debt)
                        if bs_debt > 0 and (debt is None or debt == 0):
                            debt = bs_debt
                            source = "balance_sheet"
                except Exception:
                    pass

            ratio = None
            if mcap and debt is not None and mcap > 0:
                ratio = float(debt) / float(mcap)
            else:
                source = "missing"

            rows.append({
                "ticker": t,
                "market_cap": float(mcap) if mcap else None,
                "total_debt": float(debt) if debt is not None else None,
                "debt_to_market_cap": ratio,
                "ratio_source": source,
            })
        except Exception as e:
            rows.append({
                "ticker": t,
                "market_cap": None,
                "total_debt": None,
                "debt_to_market_cap": None,
                "ratio_source": "missing",
            })

    return pd.DataFrame(rows).set_index("ticker")


def fetch_fundamentals_synthetic(
    tickers: Sequence[str],
    seed: int = 7,
) -> pd.DataFrame:
    """Generate plausible fake fundamentals for offline testing."""
    rng = np.random.default_rng(seed)
    rows = []
    for t in sorted(set(tickers)):
        local_rng = np.random.default_rng(seed + abs(hash(t)) % (2**32))
        # Most large-caps have 0-50% debt-to-mcap; some highly leveraged 60%+
        ratio = max(0.0, local_rng.beta(2, 5) * 0.8)
        mcap = float(local_rng.uniform(1e9, 5e11))
        debt = mcap * ratio
        rows.append({
            "ticker": t,
            "market_cap": mcap,
            "total_debt": debt,
            "debt_to_market_cap": ratio,
            "ratio_source": "info",
        })
    return pd.DataFrame(rows).set_index("ticker")


def fetch_fundamentals(
    tickers: Iterable[str],
    backend: str = "yfinance",
    **kwargs,
) -> pd.DataFrame:
    tickers = sorted(set(tickers))
    if backend == "yfinance":
        return fetch_fundamentals_yfinance(tickers, **kwargs)
    elif backend == "synthetic":
        return fetch_fundamentals_synthetic(tickers, **kwargs)
    raise ValueError(f"Unknown backend: {backend!r}")


def fetch_prices(
    tickers: Iterable[str],
    backend: str = "yfinance",
    **kwargs,
) -> pd.DataFrame:
    tickers = sorted(set(tickers))
    if backend == "yfinance":
        return fetch_prices_yfinance(tickers, **kwargs)
    elif backend == "synthetic":
        return fetch_prices_synthetic(tickers, **kwargs)
    raise ValueError(f"Unknown backend: {backend!r}")
