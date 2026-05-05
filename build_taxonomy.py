"""
Build the canonical 197-group taxonomy from ibd_groups.json by deterministically
pruning known overlaps. Run once to produce ibd_groups_197.json.
"""
import json
from pathlib import Path

# Documented removals to consolidate the 232-entry source into IBD's 197.
# Each removal has a one-line rationale so the choice is transparent.
REMOVALS = {
    "AUTO": ["AUTO/TRUCK-TIRES & MISC"],  # IBD folds tires/misc into REPLACEMENT PARTS
    "BANKS": ["BANKS-MONEY CENTER"],  # IBD's Super Regional already covers money centers
    "BUILDING": ["BUILDING-PAINT & ALLIED"],  # paints sit under CHEMICALS-PAINTS
    "BUSINESS_PRODUCTS": [
        "CONTAINERS-METAL/GLASS",       # consolidate containers to single group
        "CONTAINERS-PAPER/PLASTIC",
        "COMMERCIAL SVCS-MARKETING",    # overlaps ADVERTISING
        "COMMERCIAL SVCS-OUTSOURCING",  # overlaps OFFICE-OUTSOURCING SVCS
        "COMMERCIAL SVCS-PRINTING",     # overlaps MACHINERY-PRINT TRADE
    ],
    "COMPUTER": ["COMPUTER-OPTICAL RECOGNITION"],  # niche, folded into PERIPHERAL
    "CONSUMER": ["CONSUMER PRODUCTS-MISC", "CONSUMER SVCS-MISC"],  # catch-alls
    "ELECTRONICS": ["ELECTRONIC-MISC PRODUCTS"],  # catch-all
    "ENERGY": [
        "OIL&GAS-CANADIAN E&P",  # IBD groups these under INTL E&P
        "OIL&GAS-ROYALTY TRUSTS",  # niche, sits in pipeline/transport
    ],
    "FINANCE": [
        "FINANCE-PUBLISHING",  # niche; IBD puts these in MEDIA
        "REIT-DIVERSIFIED",    # consolidate into the specific REIT subgroups
        "REIT-STORAGE",        # consolidate with INDUSTRIAL/OFFICE
    ],
    "HOUSEHOLD": ["HOUSEHOLD-OFFICE FURNITURE"],  # moves to OFFICE EQUIPMENT/SUPPLIES
    "INTERNET": ["INTERNET-ISP"],  # ISPs sit in TELECOM-SVCS-DOMESTIC
    "LEISURE": ["LEISURE-SERVICES"],  # too generic
    "MACHINERY": ["MACHINERY-PRINT TRADE"],  # niche
    "MEDIA": ["MEDIA-BOOKS"],  # consolidate with PERIODICALS
    "MEDICAL": [
        "MEDICAL-DIVERSIFIED",      # catch-all
        "MEDICAL-DENTAL SUPPLIES",  # consolidate with SUPPLIES
        "MEDICAL-WHOLESALE DRUG",   # consolidate with SUPPLIES
    ],
    "METALS": ["METAL ORES-MISC"],  # catch-all
    "MINING": ["MINING-GEMS"],  # tiny universe
    "RETAIL": [
        "RETAIL-DRUG STORES",          # overlaps SUPER/MINI MARKETS for big-box
        "RETAIL-MAIL ORDER & DIRECT",  # legacy / overlaps INTERNET
        "RETAIL-MAJOR DISC CHAINS",    # overlaps DISCOUNT & VARIETY
        "RETAIL-VITAMINS/HEALTH",      # niche
    ],
    "SOFTWARE": [
        "COMPUTER SFTWR-EDU/MEDIA",    # overlaps SPECIALTY
        "COMPUTER SFTWR-MEDICAL",      # overlaps HEALTHCARE
    ],
    "TELECOM": ["TELECOM-FOREIGN SVCS"],  # consolidates with SVCS-DOMESTIC
    "TRANSPORTATION": ["TRANSPORTATION-EQUIP MFG"],  # overlaps MACHINERY
}

def build_197(src: Path, dst: Path):
    raw = json.loads(src.read_text())
    sectors_out = {}
    for sector, groups in raw["sectors"].items():
        drop = set(REMOVALS.get(sector, []))
        kept = [g for g in groups if g not in drop]
        # sanity: every removal targeted an existing entry
        missing = drop - set(groups)
        if missing:
            raise ValueError(f"{sector}: removal targets not found: {missing}")
        sectors_out[sector] = kept

    total = sum(len(v) for v in sectors_out.values())
    if total != 197:
        raise ValueError(f"Expected 197 groups after pruning, got {total}")

    out = {
        "_metadata": {
            "description": "Canonical 197 IBD-style industry groups, derived deterministically from ibd_groups.json via build_taxonomy.py",
            "total_groups": total,
            "total_sectors": len(sectors_out),
            "removals_documented_in": "build_taxonomy.py REMOVALS dict",
        },
        "sectors": sectors_out,
    }
    dst.write_text(json.dumps(out, indent=2))
    print(f"Wrote {dst} with {total} groups across {len(sectors_out)} sectors")

if __name__ == "__main__":
    here = Path(__file__).parent
    build_197(here / "ibd_groups.json", here / "ibd_groups_197.json")
