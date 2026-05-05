"""
Command-line driver for the IBD-style Industry Group Rank model.

Usage:
    # Live data (requires internet + yfinance):
    python rank.py --backend yfinance --out group_ranks.csv

    # Offline test with synthetic prices:
    python rank.py --backend synthetic --out group_ranks.csv

    # Pretty top-N report:
    python rank.py --backend yfinance --top 30
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from prices import fetch_prices
from ranking import rank_groups, build_stock_table


def load_taxonomy(path: Path) -> dict:
    return json.loads(path.read_text())["sectors"]


def load_constituents(path: Path) -> dict:
    raw = json.loads(path.read_text())
    raw.pop("_metadata", None)
    return raw


def all_tickers(constituents: dict) -> list[str]:
    seen: set[str] = set()
    for groups in constituents.values():
        for tickers in groups.values():
            seen.update(tickers)
    return sorted(seen)


def merge_taxonomy_and_constituents(taxonomy: dict, constituents: dict) -> dict:
    """Return {sector: {group: [tickers]}}, ensuring every taxonomy group
    appears (with [] if no constituents are mapped)."""
    out: dict = {}
    for sector, groups in taxonomy.items():
        out[sector] = {}
        sector_const = constituents.get(sector, {})
        for group in groups:
            out[sector][group] = list(sector_const.get(group, []))
    return out


def main():
    here = Path(__file__).parent
    p = argparse.ArgumentParser(description="IBD-style Industry Group Rank")
    p.add_argument("--taxonomy", default=str(here / "ibd_groups_197.json"))
    p.add_argument("--constituents", default=str(here / "constituents.json"))
    p.add_argument("--backend", choices=["yfinance", "synthetic"], default="yfinance")
    p.add_argument("--out", default=str(here / "group_ranks.csv"))
    p.add_argument("--out-stocks", default=str(here / "stocks.csv"),
                   help="Per-stock detail CSV (ticker, group, RS rating, …)")
    p.add_argument("--out-meta", default=str(here / "meta.json"),
                   help="Run metadata: data source, timestamp, etc.")
    p.add_argument("--top", type=int, default=20, help="Print top-N to stdout")
    p.add_argument("--bottom", type=int, default=10, help="Print bottom-N to stdout")
    p.add_argument("--rs-weight", type=float, default=0.6)
    p.add_argument("--trend-weight", type=float, default=0.4)
    args = p.parse_args()

    taxonomy = load_taxonomy(Path(args.taxonomy))
    constituents = load_constituents(Path(args.constituents))
    full_map = merge_taxonomy_and_constituents(taxonomy, constituents)

    tickers = all_tickers(constituents)
    print(f"Universe: {len(tickers)} tickers across "
          f"{sum(len(g) for g in full_map.values())} groups")
    print(f"Fetching prices via backend={args.backend} …")
    prices = fetch_prices(tickers, backend=args.backend)
    print(f"Got prices for {prices.shape[1]} tickers across {prices.shape[0]} sessions")

    df = rank_groups(
        full_map,
        prices,
        rs_weight=args.rs_weight,
        trend_weight=args.trend_weight,
    )
    df.to_csv(args.out, index=False)
    print(f"\nWrote full rank table to {args.out}")

    stocks = build_stock_table(full_map, prices)
    stocks.to_csv(args.out_stocks, index=False)
    print(f"Wrote stock detail table to {args.out_stocks} "
          f"({len(stocks)} rows, "
          f"{stocks['rs_rating'].notna().sum()} with RS ratings)")

    # Record run metadata so the publisher can warn about synthetic data.
    import json
    from datetime import datetime, timezone
    meta = {
        "backend": args.backend,
        "is_real_data": args.backend == "yfinance",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "n_tickers_universe": len(tickers),
        "n_tickers_with_prices": int(prices.shape[1]),
        "n_sessions": int(prices.shape[0]),
        "rs_weight": args.rs_weight,
        "trend_weight": args.trend_weight,
    }
    Path(args.out_meta).write_text(json.dumps(meta, indent=2))
    print(f"Wrote run metadata to {args.out_meta} (backend={args.backend})")
    if args.backend != "yfinance":
        print("⚠  WARNING: Using synthetic data — DO NOT publish this output. "
              "Use --backend yfinance for real prices.")

    print(f"\nTop {args.top} groups:")
    cols = ["rank", "group", "sector", "n_with_data",
            "median_rs_rating", "price_trend_annualised", "composite_score"]
    pd.set_option("display.max_rows", None)
    pd.set_option("display.width", 160)
    print(df[cols].head(args.top).to_string(index=False))

    print(f"\nBottom {args.bottom} groups (with data):")
    with_data = df[df["n_with_data"] > 0]
    print(with_data[cols].tail(args.bottom).to_string(index=False))


if __name__ == "__main__":
    main()
