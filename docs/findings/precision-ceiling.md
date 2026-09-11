> **Promoted 2026-09-11 from the project's private analysis repo**
> (`docs/precision-ceiling.md`; frozen as of its stated vintage — numbers are reproducible
> via the scripts named inside, run against the collection described in the
> [data dictionary](../../data/README.md)). Published as-found: early errors
> are kept honestly per the [vintage audit](../ghost-ledger-vintage-audit.md).

# The precision ceiling of vehicle-side ridership data

**Status:** methodology note supporting the PRESTO/tap-level data ask.
**Date:** 2026-09-05. **Basis:** 8.55M APC load observations collected by
this project's own GTFS-RT pipeline (Aug 17 – Sep 5, 2026), the full MiWay
weekday GTFS, and the ten routes MiWay publishes (2024 Report to the
Community) used as ground truth. Every number below is reproducible from
the repository (see "Reproducing" at the end).

## The result

With the complete vehicle-side record — every load poll the feed emits —
per-route boardings can be estimated to **±23% median accuracy, and no
better, by any method we tested.** Five plausible refinements were built
and measured; each failed to beat the simple estimator it was meant to
improve. The residual error is not statistical noise or missing data: it
is *within-route ride heterogeneity* — the same bus carries 8-stop
commuter rides at 8 AM and 2-stop errand rides at 2 PM — which aggregate
load data cannot decompose. Only tap-level (fare-card) data can.

## What was built first (and validated)

From raw APC load polls, three independent per-trip quantities:

1. **Delta floor** — Σ positive load deltas. A load rise between two
   stops means someone boarded. Lower bound on boardings.
2. **Peak floor** — peak load × capacity. Everyone aboard at the load
   maximum boarded. Lower bound, immune to the sensor's 20%-of-capacity
   quantization that blinds the delta floor on quiet routes.
3. **Passenger-stops ceiling** — Σ absolute load over observed stops.
   Every rider occupies ≥1 stop, so boardings ≤ passenger-stops.
   Distribution-free upper bound.

Two estimators complete the chain: **measured-uplift** (floor ÷ capture
ratio, calibrated on the ten published routes) and the **mid estimate**
(ceiling ÷ 7.98, where 7.98 stops/ride is the all-day implied trip length
measured on the published ten, range 4.99–10.36). Backtested against
published truth: **9/10 routes within ±30%, median |error| 23%** — versus
the raw floors' 23–78% capture. All 52 auditable routes pass a
trip-length consistency audit; the uplift chain's mean implied trip
length (7.72) independently lands on the published calibration's median
(7.98).

## Five refinements, five measured failures

Each was implemented and evaluated by leave-one-out backtest on the ten
routes where truth is known:

| # | Refinement | Hypothesis | Measured result |
|---|---|---|---|
| 1 | Trip length from route distance | longer routes → longer rides | **r = 0.17.** Route 2: 7.7 km, 8.1 stops/ride. Route 109: 29 km, 7.9. Turnover doesn't scale with geometry. |
| 2 | Trip length from stop count | more stops → more turnover points | LOO median error **24.0%** vs 23.7% for the global median (R² = 0.28). A wash. |
| 3 | Coverage correction | estimates miss unobserved stops | Published routes are uniformly **0.88–0.93** observed-stop coverage — nothing to correct. |
| 4 | Blend: floor + α·(ceiling − floor) | use both anchors with fitted weight | LOO median **22.5%**, but route 109 degrades from −1% to +34%. Worse tails. |
| 5 | Ensemble: mid + uplift averaged | errors correlate 0.26 → averaging cancels | LOO median **22.6%**. Slightly better worst case, no better center. |

A sixth variant — an alighting-side tight floor (boardings ≥ Σ\|negative
deltas\|, valid because buses empty at terminals) — adds only **+1%**
capture (25.4% → 26.4%).

## Why 2 and 109 hit exactly

The two near-perfect estimates (109: −1%, 2: +1%) have implied trip
lengths of 7.87 and 8.10 — sitting *at* the 7.98 global median. They are
estimated exactly because their riders behave like the network average.
The ±25% routes are exactly those whose ride patterns differ. That is the
signature of a *structural* limit, not an engineering bug: the estimator
has no parameter left to tune.

## The wall, and what breaks it

Four independent lines of measurement now terminate at the same boundary:

1. **Transfers** — vehicle-side instruments cannot observe them.
2. **Quiet-route ridership** — the 20%-bucket sensor floor makes loads
   below resolution invisible (routes 14, 25, 31, 73, 90 flagged).
3. **Forecast contamination** — non-measured prediction rows must be
   excluded, shrinking usable data further.
4. **Trip-length precision** — within-route ride heterogeneity, the
   residual error quantified above at ±23%.

Each is a quantity only fare-card data measures directly. The ask is
therefore not "more APC data" — it is the one instrument class the
vehicle-side record cannot substitute for.

## What tap data would buy, concretely

- Per-route boardings: **±23% → exact** (tap counts are counts).
- Transfer rates and the boardings-vs-journeys bridge: measurable at
  all (currently inferred only, via CUTA peer ratios at 1.32–1.34).
- Trip-length distributions per route/period: the parameter this note
  shows cannot be recovered from loads.
- Equity weighting for the 154 stops served only by
  below-APC-resolution routes: unknown today, not zero.

## Reproducing

```bash
cd backend
python scripts/reconstruct_boardings.py            # floors + ceiling
python scripts/build_ridership_dataset.py          # estimates + backtest
# backtest line: "mid-estimator backtest ... median |err| 23%"
```

The per-route numbers in this note come from `app/data/ridership.csv`
(`implied_trip_length`, `estimate_mid`, `estimate_upper`,
`measured_lower_bound`, `estimate_method`) and the LOO experiments logged
in `.agents/KNOWN-TRUTHS.md` (2026-09-05 entries).
