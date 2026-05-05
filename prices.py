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
