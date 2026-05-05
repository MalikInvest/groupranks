"""
Shariah-status engine for the constituent universe.

Every ticker gets one of three statuses:
    HALAL          — passes business-activity screen and (where checked)
                     financial ratios per AAOIFI methodology
    QUESTIONABLE   — passes business screen but financial ratios are borderline
                     OR business screen is mixed (small impure-revenue exposure)
                     OR data is incomplete; case-by-case review needed
    HARAM          — fails business-activity screen (core business is in a
                     non-permissible sector) — no financial-ratio rescue possible

This module is intentionally conservative. Where there's doubt, default to
QUESTIONABLE. Final classifications should be cross-checked against Musaffa,
Zoya, or a Shariah scholar — this is a model, not a fatwa.

Methodology references:
    AAOIFI Shariah Standard No. 21 (Financial Paper / Shares and Bonds)
    AAOIFI Shariah Standard No. 59 (Sale of Debt)
    Three financial ratios, all measured against market capitalisation:
        1. Interest-bearing debt / market cap   ≤ 30%
        2. Interest-bearing securities / market cap   ≤ 30%
        3. Impure (interest + haram) income / total income   ≤ 5%
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

# IBD-style group → default Shariah classification.
# This is the FIRST line of screening (business-activity test).
# Any ticker in a HARAM group is HARAM regardless of financials.
# Any ticker in a HALAL group still goes through financial-ratio review.
GROUP_DEFAULTS: dict[str, str] = {
    # ---- HARAM by core business ----
    "BANKS-FOREIGN":              "HARAM",
    "BANKS-MIDWEST":              "HARAM",
    "BANKS-NORTHEAST":            "HARAM",
    "BANKS-SOUTHEAST":            "HARAM",
    "BANKS-SUPER REGIONAL":       "HARAM",
    "BANKS-WEST/SOUTHWEST":       "HARAM",
    "SAVINGS & LOAN":             "HARAM",
    "BEVERAGES-ALCOHOLIC":        "HARAM",
    "TOBACCO":                    "HARAM",
    "LEISURE-GAMING/EQUIPMENT":   "HARAM",
    "INSURANCE-ACC & HEALTH":     "HARAM",  # conventional insurance
    "INSURANCE-BROKERS":          "HARAM",
    "INSURANCE-DIVERSIFIED":      "HARAM",
    "INSURANCE-LIFE":             "HARAM",
    "INSURANCE-PROP/CAS/TITLE":   "HARAM",
    "FINANCE-CONSUMER LOANS":     "HARAM",
    "FINANCE-MORTGAGE & RELATED SVC": "HARAM",
    "REIT-MORTGAGE":              "HARAM",  # mortgage REITs are interest-based
    "FINANCE-INVESTMENT BANKS/BROKERS": "HARAM",  # interest-bearing core
    # FINANCE-CREDIT CARD/PAYMENT and FINANCE-INVESTMENT MGMT are mixed:
    # payment processors (V, MA, SQ) are usually OK, lenders are not.
    # We mark the group QUESTIONABLE and override per-ticker below.

    # ---- QUESTIONABLE by core business (mixed, borderline, or scholar-disputed) ----
    "FINANCE-CREDIT CARD/PAYMENT":     "QUESTIONABLE",
    "FINANCE-INVESTMENT MGMT":         "QUESTIONABLE",
    "FINANCE-SERVICES":                "QUESTIONABLE",  # exchanges, ratings agencies — mixed
    "FINANCE-ETFS/CLOSED-END FUNDS":   "QUESTIONABLE",
    "FINANCE-PUBLISHING":              "QUESTIONABLE",
    "MEDIA-CABLE/SATELLITE TV":        "QUESTIONABLE",  # often carry haram content
    "MEDIA-DIVERSIFIED":               "QUESTIONABLE",
    "MEDIA-RADIO/TV":                  "QUESTIONABLE",
    "LEISURE-MOVIES & RELATED":        "QUESTIONABLE",  # adult/haram-leaning content
    "LEISURE-HOTELS & MOTELS":         "QUESTIONABLE",  # alcohol revenue typical
    "LEISURE-RESTAURANTS":             "QUESTIONABLE",  # alcohol revenue typical
    "AEROSPACE-DEFENSE":               "QUESTIONABLE",  # weapons sales — scholar-debated
    "AEROSPACE-DEFENSE EQUIPMENT":     "QUESTIONABLE",
    "ELECTRONIC-MILITARY SYSTEMS":     "QUESTIONABLE",
    "FOOD-MEAT PRODUCTS":              "QUESTIONABLE",  # pork exposure unclear without filings
    "INTERNET-CONTENT":                "QUESTIONABLE",  # adult/ad revenue varies
    "COMPUTER SFTWR-GAMING":           "QUESTIONABLE",
    # All other groups default to HALAL_PENDING_FINANCIALS, see is_halal_default.
}

# Sector-level fallback for groups not in GROUP_DEFAULTS — most are
# pending-financials (treated as HALAL until financials prove otherwise).
SECTOR_DEFAULTS: dict[str, str] = {
    "BANKS":     "HARAM",
    "INSURANCE": "HARAM",
    "FINANCE":   "QUESTIONABLE",  # mixed sector
}

# Per-ticker overrides: corrects mistakes the group default makes.
# Curated using public Shariah-screener consensus (Musaffa, Zoya, Islamicly)
# as of late-2025 reviews. These should be re-validated quarterly.
TICKER_OVERRIDES: dict[str, tuple[str, str]] = {
    # Format: ticker -> (status, reason)

    # --- Payment processors: typically halal core business ---
    "V":      ("HALAL",        "Payment network — fee-based revenue, no lending"),
    "MA":     ("HALAL",        "Payment network — fee-based revenue, no lending"),
    "PYPL":   ("QUESTIONABLE", "Mixed: fee revenue plus credit/BNPL exposure"),
    "SQ":     ("QUESTIONABLE", "Square: fee-based core, some lending exposure"),
    "AFRM":   ("HARAM",        "Pure BNPL/lending business model"),
    "AXP":    ("HARAM",        "Charge card with interest-based credit operations"),
    "DFS":    ("HARAM",        "Discover — credit-card lender"),
    "SYF":    ("HARAM",        "Synchrony — consumer credit"),
    "ALLY":   ("HARAM",        "Ally — auto-loan bank"),
    "GPN":    ("HALAL",        "Global Payments — pure payment processor"),
    "FIS":    ("HALAL",        "Fidelity National Information — bank tech, fee revenue"),
    "FISV":   ("HALAL",        "Fiserv — payment/fintech infrastructure"),
    "TOST":   ("HALAL",        "Toast — restaurant tech/payments"),

    # --- Financial data and exchanges (typically halal — fee-based) ---
    "MCO":    ("HALAL",        "Moody's — ratings/data, fee revenue"),
    "MSCI":   ("HALAL",        "MSCI — index/data, fee revenue"),
    "SPGI":   ("HALAL",        "S&P Global — data/ratings"),
    "ICE":    ("QUESTIONABLE", "ICE — exchange ops with mortgage-tech (BlackKnight) exposure"),
    "CME":    ("HALAL",        "CME — derivatives exchange (futures themselves debated, but core is fee-based)"),
    "NDAQ":   ("HALAL",        "Nasdaq — exchange operator"),
    "FDS":    ("HALAL",        "FactSet — financial data subscription"),

    # --- Asset managers: usually halal but check fund mix ---
    "BLK":    ("QUESTIONABLE", "BlackRock — large fixed-income/bond fund manager"),
    "BX":     ("QUESTIONABLE", "Blackstone — alt-asset manager, real-estate debt exposure"),
    "KKR":    ("QUESTIONABLE", "KKR — private equity with credit business"),
    "APO":    ("QUESTIONABLE", "Apollo — credit-heavy alt manager"),
    "TROW":   ("HALAL",        "T. Rowe Price — equity-fund-focused"),
    "BEN":    ("HALAL",        "Franklin Resources"),
    "ARES":   ("HARAM",        "Ares — credit-focused alt manager"),
    "OWL":    ("QUESTIONABLE", "Blue Owl — direct-lending business"),

    # --- Berkshire: scholar-disputed (insurance core, but very large) ---
    "BRK-A":  ("QUESTIONABLE", "Berkshire — large insurance subsidiaries; scholar-disputed"),
    "BRK-B":  ("QUESTIONABLE", "Berkshire — large insurance subsidiaries; scholar-disputed"),

    # --- Defense names — Musaffa typically marks compliant if ratios pass,
    #     Zoya often non-compliant. Mark questionable for transparency. ---
    "LMT":    ("QUESTIONABLE", "Defense — scholar-disputed, financials typically pass AAOIFI"),
    "RTX":    ("QUESTIONABLE", "Defense — scholar-disputed"),
    "NOC":    ("QUESTIONABLE", "Defense — scholar-disputed"),
    "GD":     ("QUESTIONABLE", "Defense — scholar-disputed"),
    "BA":     ("QUESTIONABLE", "Boeing — commercial + defense, debt ratio borderline"),
    "LHX":    ("QUESTIONABLE", "L3Harris — defense"),
    "HII":    ("QUESTIONABLE", "Huntington Ingalls — naval defense"),

    # --- Hospitality/restaurants: alcohol revenue is the issue ---
    "MCD":    ("QUESTIONABLE", "Some alcohol revenue in international markets"),
    "SBUX":   ("HALAL",        "No alcohol/pork in core menu"),
    "CMG":    ("QUESTIONABLE", "Some alcohol revenue (margaritas, beer)"),
    "DPZ":    ("HALAL",        "Domino's — pizza, no alcohol"),
    "WEN":    ("HALAL",        "Wendy's — quick service, no alcohol"),
    "YUM":    ("QUESTIONABLE", "KFC/Pizza Hut/Taco Bell — pork in some menus"),
    "QSR":    ("QUESTIONABLE", "Restaurant Brands — pork in some menus"),
    "SHAK":   ("QUESTIONABLE", "Beer/wine on menu"),
    "TXRH":   ("HARAM",        "Texas Roadhouse — significant alcohol revenue"),
    "DRI":    ("HARAM",        "Darden — Olive Garden etc., heavy alcohol revenue"),
    "BLMN":   ("HARAM",        "Bloomin' Brands — Outback steakhouse, alcohol"),
    "EAT":    ("HARAM",        "Brinker — Chili's, alcohol revenue"),
    "MAR":    ("QUESTIONABLE", "Marriott — alcohol/pork revenue at properties"),
    "HLT":    ("QUESTIONABLE", "Hilton — alcohol/pork revenue at properties"),
    "H":      ("QUESTIONABLE", "Hyatt — alcohol/pork revenue at properties"),

    # --- Tech megacaps that often have borderline financials ---
    "AAPL":   ("HALAL",        "Core business halal; impure revenue (Apple Card) typically <5%"),
    "MSFT":   ("HALAL",        "Software/cloud — halal core; financials typically pass"),
    "GOOGL":  ("QUESTIONABLE", "Ad-revenue exposure to non-halal advertisers"),
    "GOOG":   ("QUESTIONABLE", "Same as GOOGL"),
    "META":   ("QUESTIONABLE", "Ad-revenue exposure including non-halal content/ads"),
    "AMZN":   ("HALAL",        "E-commerce + AWS halal core; AWS dominant"),
    "NVDA":   ("HALAL",        "Semiconductors — halal core"),
    "TSLA":   ("HALAL",        "Auto manufacturer — halal core; financing arm small"),
    "NFLX":   ("HARAM",        "Streaming content includes substantial haram material"),
    "DIS":    ("QUESTIONABLE", "Mixed content; scholar-disputed"),

    # --- Healthcare REITs: typically OK; mortgage-style REITs not ---
    # Already handled at group level (REIT-MORTGAGE = HARAM)

    # --- Streaming/content ---
    "SPOT":   ("QUESTIONABLE", "Streaming — music revenue debated"),
    "RBLX":   ("QUESTIONABLE", "Gaming platform — mixed content"),

    # --- Auto / EV ---
    "F":      ("QUESTIONABLE", "Ford — high debt ratio plus Ford Credit lending arm"),
    "GM":     ("QUESTIONABLE", "GM — GM Financial lending arm"),
    "RIVN":   ("HALAL",        "Rivian — pure EV manufacturer"),
    "LCID":   ("HALAL",        "Lucid — pure EV manufacturer"),

    # --- Energy: usually halal core ---
    "XOM":    ("HALAL",        "Integrated oil"),
    "CVX":    ("HALAL",        "Integrated oil"),
    # Coal — scholars debate environmental concerns but AAOIFI doesn't exclude
}


@dataclass
class Status:
    status: str   # "HALAL", "QUESTIONABLE", or "HARAM"
    reason: str
    source: str   # how we arrived at this — "override", "group", "sector", "default"


def classify_ticker(
    ticker: str,
    sector: str,
    group: str,
    debt_to_mcap: float | None = None,
) -> Status:
    """Return a Shariah status for a single ticker.

    Resolution order:
      1. Per-ticker override (always wins)
      2. Group default
      3. Sector default
      4. HALAL (business activity permissible)

    Then, if a debt-to-market-cap ratio is provided AND the status is currently
    HALAL, we apply a financial-ratio refinement:
      - ratio > 0.33  → downgrade HALAL to QUESTIONABLE
                        (business OK but balance sheet exceeds AAOIFI threshold)
      - ratio <= 0.33 → keep HALAL but enrich the reason with "ratio verified"

    HARAM and QUESTIONABLE business-activity classifications are NEVER
    upgraded to HALAL by the ratio check — financial ratios cannot rescue
    an impermissible core business.
    """
    # ---- step 1-4: business-activity classification ----
    if ticker in TICKER_OVERRIDES:
        s, r = TICKER_OVERRIDES[ticker]
        base = Status(s, r, "override")
    elif group in GROUP_DEFAULTS:
        s = GROUP_DEFAULTS[group]
        base = Status(s, f"Group classification: {group}", "group")
    elif sector in SECTOR_DEFAULTS:
        s = SECTOR_DEFAULTS[sector]
        base = Status(s, f"Sector classification: {sector}", "sector")
    else:
        base = Status(
            "HALAL",
            "Business activity permissible",
            "default",
        )

    # ---- ratio refinement (only applies to HALAL business-activity verdicts) ----
    if debt_to_mcap is None:
        # We don't have a ratio. Keep base status but be transparent.
        if base.status == "HALAL":
            return Status(
                base.status,
                base.reason + " — debt ratio not verified, cross-check Musaffa/Zoya",
                base.source,
            )
        return base

    if base.status != "HALAL":
        # HARAM or QUESTIONABLE business activity: ratio doesn't matter.
        return base

    # We have a ratio AND business activity is permissible.
    if debt_to_mcap > 0.33:
        return Status(
            "QUESTIONABLE",
            f"Business OK but debt/market-cap ratio {debt_to_mcap:.0%} exceeds AAOIFI 33% threshold",
            base.source + "+ratio",
        )
    else:
        return Status(
            "HALAL",
            f"Business OK; debt/market-cap ratio {debt_to_mcap:.0%} (under AAOIFI 33%)",
            base.source + "+ratio",
        )


def classify_all(
    constituents: Mapping[str, Mapping[str, Iterable[str]]],
    debt_ratios: Mapping[str, float] | None = None,
) -> dict[str, Status]:
    """Classify every (ticker, group) pair in the constituent map.

    `debt_ratios` is an optional {ticker: debt_to_market_cap} mapping. When
    provided, HALAL-by-business-activity tickers get downgraded to QUESTIONABLE
    if their ratio exceeds 33%.
    """
    debt_ratios = debt_ratios or {}
    out: dict[str, Status] = {}
    for sector, groups in constituents.items():
        for group, tickers in groups.items():
            for t in tickers:
                key = f"{t}|{group}"
                ratio = debt_ratios.get(t)
                out[key] = classify_ticker(t, sector, group, ratio)
    return out


def group_summary(
    constituents: Mapping[str, Mapping[str, Iterable[str]]],
    debt_ratios: Mapping[str, float] | None = None,
) -> dict[str, dict[str, float]]:
    """Per-group counts: {group: {halal, questionable, haram, total, pct_halal}}."""
    debt_ratios = debt_ratios or {}
    summary: dict[str, dict] = {}
    for sector, groups in constituents.items():
        for group, tickers in groups.items():
            counts = {"HALAL": 0, "QUESTIONABLE": 0, "HARAM": 0}
            n = 0
            for t in tickers:
                ratio = debt_ratios.get(t)
                st = classify_ticker(t, sector, group, ratio)
                counts[st.status] += 1
                n += 1
            summary[group] = {
                "halal":        counts["HALAL"],
                "questionable": counts["QUESTIONABLE"],
                "haram":        counts["HARAM"],
                "total":        n,
                "pct_halal":    counts["HALAL"] / n if n else 0.0,
            }
    return summary
