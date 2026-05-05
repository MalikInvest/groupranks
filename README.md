# Malik Invest · Industry Group Rankings

A free, weekly-refreshed industry-group ranking page with AAOIFI-aligned
Shariah classifications. Designed as a top-of-funnel asset for Malik
Invest — drives email signups for the paid weekly research.

## What it does

US equities are divided into 197 narrow industry groups. Each group is ranked
1 (strongest) to 197 (weakest) using a 6-month weighted relative-strength
formula across constituent stocks. Every constituent is also screened for
Shariah status using AAOIFI methodology.

The published HTML page is interactive: click any group to see its stocks,
sorted by RS rating with halal/questionable/haram badges; click any ticker
for a chart and the Shariah reasoning. A toggle filters to halal-leaning
groups so visitors who only want compliant ideas can ignore the noise.

A built-in CTA collects email addresses for the weekly research — currently
wired to a `mailto:` fallback, ready for a real CRM endpoint when you're set up.

## What's in the box

```
.
├── ibd_groups.json           # source taxonomy (sector → groups)
├── build_taxonomy.py         # deterministic prune to exactly 197 groups
├── ibd_groups_197.json       # the canonical 197-group taxonomy
├── constituents.json         # ticker → group map (~1,250 stocks)
├── shariah.py                # AAOIFI screening engine
├── prices.py                 # yfinance + synthetic backends
├── ranking.py                # RS formula, group scoring, ranking
├── rank.py                   # CLI: produces group_ranks.csv + stocks.csv
├── publish_html.py           # CLI: produces the branded HTML page
├── test_ranking.py           # unit tests
├── group_ranks.csv           # sample group-level output
├── stocks.csv                # sample stock-level output (with Shariah cols)
└── group_ranks.html          # sample published page (Malik Invest branded)
```

## Methodology

### Relative-strength ranking

Per-stock 6-month weighted RS:
```
RS = 0.4·(P/P₋₆₅) + 0.2·(P/P₋₁₃₀) + 0.2·(P/P₋₁₉₅) + 0.2·(P/P₋₂₆₀)
```
Converted to a 1–99 percentile rating against the universe. Per-group
score is the annualised slope of `log(Σ prices)` fit by least squares
over the last ~6 months. Composite z-score blends median RS rating (60%)
with price-trend slope (40%).

### Shariah classification (AAOIFI Standard No. 21)

Each ticker gets one of three statuses:

- **Halal** — business activity is permissible, financial ratios pass
  (debt ≤30% of market cap, interest-bearing assets ≤30%, impure income
  ≤5% of total income).
- **Questionable** — passes business screen but financials are borderline,
  or business has small impure-revenue exposure, or the case is
  scholar-disputed (e.g., defense, conventional media).
- **Haram** — fails the business-activity screen (banking, insurance,
  alcohol, tobacco, gambling, conventional lending, mortgage REITs).

Resolution order: per-ticker override → group default → sector default →
permissible default. The override list (`shariah.py`) corrects mistakes the
group default makes (e.g., V is HALAL even though
FINANCE-CREDIT-CARD-PAYMENT is mixed; AFRM is HARAM in the same group).

This is a **model, not a fatwa**. It's intended to surface candidates for
further screening, not to replace consultation with a scholar or
established Shariah-screening services (Musaffa, Zoya, Islamicly).

## Quick start

```bash
pip install pandas numpy yfinance

# Live data (needs internet):
python rank.py --backend yfinance
python publish_html.py

# Offline test with synthetic prices:
python rank.py --backend synthetic
python publish_html.py

# Run unit tests:
python test_ranking.py
```

## Lead-capture wiring

The CTA form currently uses `mailto:` to open the user's email client with
a pre-filled subscription message. To wire it to a real CRM (Mailchimp,
ConvertKit, Beehiiv, etc.), find this block in `publish_html.py`'s `JS`
variable:

```javascript
const subj = encodeURIComponent('Subscribe to Malik Invest weekly');
const body = encodeURIComponent(`Please add ${email} to the Malik Invest weekly research list.`);
window.location.href = `mailto:hello@malikinvest.com?subject=${subj}&body=${body}`;
```

Replace with a `fetch()` to your provider's signup endpoint, e.g.:

```javascript
const res = await fetch('https://api.mailchimp.com/3.0/lists/<list_id>/members', {
  method: 'POST',
  headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer <token>'},
  body: JSON.stringify({email_address: email, status: 'subscribed'})
});
```

For Beehiiv (often a better fit for paid newsletters) the embeddable form
is even simpler — they give you an HTML snippet you can paste in place of
the form element.

## Refresh cadence

Friday after market close, weekly. Cron snippet:

```cron
# Every Friday at 5 PM Eastern (22:00 UTC)
0 22 * * 5  cd /path/to/malik-invest-rankings && \
  python rank.py --backend yfinance && \
  python publish_html.py && \
  scp group_ranks.html user@host:/var/www/rankings/index.html
```

GitHub Actions equivalent if you want to skip the VPS — same commands, on a
scheduled workflow that commits the output back to a `gh-pages` branch.

## Caveats

The same caveats from the methodology document apply: the 197-group
taxonomy is a reconstruction, the constituent map skews to large/mid-caps,
the Shariah classifications need quarterly review (financial ratios shift),
and survivorship bias is present. Fine for a free lead-magnet; not yet
ready to be the basis of paid stock recommendations.

## Disclaimer

Nothing here is investment advice. Shariah classifications are a model and
should be cross-checked. © Malik Invest.
