> **Promoted 2026-09-11 from the project's private analysis repo**
> (`docs/ridership-band-lyu.md`; frozen as of its stated vintage — numbers are reproducible
> via the scripts named inside, run against the collection described in the
> [data dictionary](../../data/README.md)). Published as-found: early errors
> are kept honestly per the [vintage audit](../ghost-ledger-vintage-audit.md).

# Ridership-impact band, re-derived from Lyu & Yan (2025) OTP elasticities

_Date: 2026-09-06 · Companion to `exec-summary.md`'s ridership projection ·
Reproduce with `python scripts/ridership_band_lyu.py` (reads the frozen
`exec-summary.json`, prints the band, changes nothing)._

## Why re-derive

The incumbent band (+1.94%, plausible range 0.39–10.44%) chains two old
estimates: a 1999 wait-time premium (Pratt/VTPI, 2–5×) into a 2005 Portland
**travel-time** elasticity (Dowling, −0.13, band −0.05…−0.30). Neither is
wrong, but the chain never measures what the optimizer actually produces —
**on-time performance** — and the elasticity is pre-pandemic, from a different
demand regime.

The strongest available alternative measures exactly that variable:
**Lyu & Yan, "Analyzing the Impact of Service Frequency and On-time
Performance on Transit Ridership in Miami-Dade County"** (arXiv 2511.07467,
archived at `docs/sources/lyu-yan-miami-dade-otp-ridership-arxiv2511.pdf`,
sha256 `8433c63f4fddb6f6…`): a route-level panel of APC ridership + GTFS-RT
performance with two-way fixed effects, whose log-log coefficients are
**direct on-time-rate elasticities** — and whose recovery-period (2021–23)
estimates come from the same post-pandemic demand restructuring MiWay is
living through now.

## The derivation

From the frozen exec-summary artifact (2,789 → 2,456 missed of 6,000 measured
transfers):

```
transfer on-time rate:  53.5% → 59.1%
relative OTP gain:      59.1 / 53.5 − 1 = +10.37%
ridership gain:         +10.37% × elasticity
```

| Coefficient (Lyu & Yan, recovery period) | Projected ridership gain |
|---|---|
| +0.584 (AM peak, p=0.045) — **high** | **+6.06%** |
| **+0.417 (system-wide, p=0.031) — central** | **+4.32%** |
| +0.266 (PM peak) — **low** | **+2.76%** |
| ≈0 (pre-COVID, insignificant) — **floor** | 0.00% |

**Re-derived band: +4.3% central, +2.8% to +6.1% plausible** (floor 0). The
incumbent band's central estimate (+1.94%) sits *below* this one's low end —
the two chains agree the sign is positive; they disagree about magnitude.

## Which number to quote

Keep the incumbent band as the headline (it is the conservative, long-established
chain, and every downstream doc and the quote gate pin it). Quote the Lyu band
as the **modern upper-anchored alternative**: "a 2025 route-level study
post-pandemic elasticities imply up to +4.3% (2.8–6.1%)". If asked for the
most defensible single sentence: *the savings are worth between 1.9% and 4.3%
ridership depending on which elasticity generation you believe, and both
generations agree it is materially positive.*

## Honest caveats (all material, none fatal)

1. **Different agency.** Miami-Dade: ~2× MiWay's ridership, heavy rail plus
   bus, different fare structure and demographics. Route-level elasticities
   transfer imperfectly across networks.
2. **Unit mismatch.** Lyu's OTP is route-level *running* on-time performance;
   ours is *scheduled-transfer* success (realized wait vs plan on specific
   stop-pairs). Cousins, not the same variable — the transfer measure may be
   more visible to riders (a missed transfer is a worse event than a
   mid-route delay), which would bias our projection *up*, not down.
3. **Correlation, not causation.** Two-way fixed effects absorb route and
   year confounders, but service changes correlate with demand in ways the
   design cannot fully remove.
4. **Recovery-era regime.** Coefficients were estimated while ridership was
   *growing* back; MiWay 2026 is *shrinking* (student-cap demand shock,
   −24% student ridership). Elasticities in a declining market are generally
   smaller — treat the AM-peak high anchor (+6.1%) as optimistic.
5. **Single study, modest significance** (p = 0.031–0.045). One paper is a
   strong prior-updater, not a consensus.
6. **No fare effect.** Both bands exclude the Jan-1 and Sept-1 2026 fare
   changes, which push the opposite direction and confound any before/after
   measurement this winter.

## Method notes

- Input: `docs/exec-summary.json` only — the same frozen artifact the prose
  quotes; no re-solve, no data re-read, so the band can never drift from the
  headline figures.
- The script writes nothing. The quote gate remains the single authority on
  what prose may claim; amend prose only after pasting the script's printed
  JSON into this file.
- Elasticity source values and p-values: Lyu & Yan Table 3 (system) and
  Table 4 (peak splits), archived PDF pp. 14–17.
