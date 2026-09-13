> **Promoted 2026-09-11 from the project's private analysis repo**
> (`docs/validation-study.md`; frozen as of its stated vintage — numbers are reproducible
> via the scripts named inside, run against the collection described in the
> [data dictionary](../../data/README.md)). Published as-found: early errors
> are kept honestly per the [vintage audit](../ghost-ledger-vintage-audit.md).

> **Re-promoted 2026-09-11** after the private source gained a basis-
> provenance box (Monte Carlo section) — restored following the DEC-13
> retroactive audit; the promotion follows its source.

> **Re-promoted 2026-09-11 (2nd):** private source corrected the canonical
> Monte Carlo p5 to +696.6 / p95 +876.3 (the run's own JSON values; the
> raw historical -10.5 was already superseded by the Sept 5 erratum).

# MiWay Transit Optimizer — validation study

Run on the bundled weekday feed, **Midday** period, solver **OPTIMAL**, 6,000 connections. Complements `docs/validation-report.md` (closed-form sensitivity) and `docs/exec-summary.md` (council one-pager).

> No observed (AVL/GTFS-RT) wait data is bundled with this feed, so a true predicted-vs-actual comparison is not possible here. The sections above are the closest honest proxies: cross-period stability of the predicted ranking, and the distribution of predicted gains under realistic lateness noise. Re-run with ``--rt-csv`` (see ``app/realtime.py``) to replace the noise model with real observed lateness.

## 1. Cross-period consistency of the worst-missed picture

Across the feed's three service patterns (weekday / Saturday / Sunday), the top-10 worst-missed transfers contain **23 distinct (stop, route-pair) groups**, of which **5** appear on two or more days. 
The worst misses are a stable, recurring set — a single-day ranking is not a fluke.

**Weekday** top misses:

| Stop | Routes | Wait | Headway | Cost | Reason |
|---|---|---|---|---|---|
| City Centre Transit Terminal Platform D | 66 → 68 | 18 min | 73.9 min | 24.9 | too long |
| City Centre Transit Terminal Platform D | 61 → 68 | 19 min | 73.9 min | 23.1 | too long |
| City Centre Transit Terminal Platform D | 2 → 68 | 20 min | 73.9 min | 23.1 | too long |
| City Centre Transit Terminal Platform D | 109 → 68 | 19 min | 73.9 min | 22.2 | too long |
| City Centre Transit Terminal Platform D | 66 → 6 | 17 min | 28.8 min | 20.8 | too long |
| City Centre Transit Terminal Platform D | 66 → 9 | 19 min | 26.7 min | 19.5 | too long |
| City Centre Transit Terminal Platform D | 3 → 68 | 15 min | 73.9 min | 19.4 | too long |
| City Centre Transit Terminal Platform D | 28 → 68 | 19 min | 73.9 min | 19.4 | too long |
| City Centre Transit Terminal Platform D | 2 → 6 | 18 min | 28.8 min | 19.2 | too long |
| City Centre Transit Terminal Platform D | 17 → 68 | 20 min | 73.9 min | 18.4 | too long |

**Saturday** top misses:

| Stop | Routes | Wait | Headway | Cost | Reason |
|---|---|---|---|---|---|
| City Centre Transit Terminal Platform D | 66 → 6 | 15 min | 43.8 min | 32.6 | too long |
| City Centre Transit Terminal Platform D | 61 → 6 | 14 min | 43.8 min | 30.6 | too long |
| City Centre Transit Terminal Platform D | 2 → 6 | 20 min | 43.8 min | 30.4 | too long |
| Eglinton Ave At Dixie Rd | 35 → 5 | 18 min | 25.7 min | 29.7 | too long |
| City Centre Transit Terminal Platform D | 109 → 6 | 18 min | 43.8 min | 29.5 | too long |
| City Centre Transit Terminal Platform D | 66 → 28 | 17 min | 29.9 min | 29 | too long |
| Derry Rd At Tomken Rd | 42 → 51 | 20 min | 44.6 min | 28.4 | too long |
| City Centre Transit Terminal Platform D | 61 → 28 | 16 min | 29.9 min | 27.2 | too long |
| City Centre Transit Terminal Platform D | 2 → 28 | 17 min | 29.9 min | 27 | too long |
| City Centre Transit Terminal Platform D | 109 → 28 | 15 min | 29.9 min | 26.2 | too long |

**Sunday** top misses:

| Stop | Routes | Wait | Headway | Cost | Reason |
|---|---|---|---|---|---|
| City Centre Transit Terminal Platform D | 66 → 6 | 13 min | 45.1 min | 37.2 | too long |
| Eglinton Ave At Dixie Rd | 35 → 5 | 21 min | 30.1 min | 36.9 | too long |
| City Centre Transit Terminal Platform D | 2 → 6 | 15 min | 45.1 min | 35.6 | too long |
| Dixie Rd At Matheson Blvd | 5 → 39 | 22 min | 43.1 min | 34.2 | too long |
| City Centre Transit Terminal Platform D | 61 → 6 | 21 min | 45.1 min | 33.8 | too long |
| Dundas St At Dixie Rd | 1 → 5 | 15 min | 30.1 min | 33.6 | too long |
| City Centre Transit Terminal Platform D | 109 → 6 | 17 min | 45.1 min | 32.9 | too long |
| Dundas St East Of Dixie Rd | 1 → 5 | 19 min | 30.1 min | 32.9 | too long |
| Living Arts Dr At City Centre Dr | 26 → 6 | 14 min | 45.1 min | 32 | too long |
| City Centre Transit Terminal Platform D | 26 → 6 | 13 min | 45.1 min | 32 | too long |

## 2. Realized gain under lateness — Monte Carlo distribution

> **Basis provenance (restored 2026-09-11, per DEC13-retroactive-audit):** the
> **canonical** Monte Carlo basis cited by `RUN-OF-RECORD.md` (DEC-04) is the
> pre-Sept-7 run: **338,667 observed departures, 500 simulated days, median
> +785 min/day saved (p5 +696.6, p95 +876.3), 100% of simulated days positive**
> — computed on the frozen Aug 17–23 lateness pool. A Sept 9 regeneration
> replaced this section's table on a newer lateness pool; that newer table
> is a *different-vintage measurement*, not a correction of the canonical
> run. Quote the canonical basis for pre-Sept-7 claims; quote the newer
> table only with its own vintage stated.

Simulated operating days where each connection's wait is perturbed by realistic lateness. Savings use the solver's own metric (passenger-facing wait, missed connection = +1 headway) — the same quantity the dashboard's "passenger-minutes saved" reports. Positive = the re-timed plan beat today's schedule that day.

| Lateness model | Median day | 5th pct | 95th pct | Days re-timed wins | Beats paper gain |
|---|---|---|---|---|---|
| parametric Laplace (mean lateness 1 min) | +6,432 min | +6,224 min | +6,638 min | 100.0% | 100.0% |
| parametric Laplace (mean lateness 2 min) | +5,091 min | +4,849 min | +5,351 min | 100.0% | 1.6% |

**Reading it:** the median and win-probability columns are the numbers to quote; the observed-lateness simulation is the ground-truth version of the parametric story in `docs/validation-report.md`. Re-run without ``--rt-csv`` for the parametric comparison.

## 3. Does the plan help where real riders are?

The route-level winners/losers were recomputed weighted by **boarding figures** (57 routes: published APC where available, calibrated estimates elsewhere) instead of frequency estimates. Rank correlation of per-route impact: **0.603** over 56 routes (1.0 = identical priorities).

Top-10 winners under the two weightings overlap on **7/10** routes: 10, 2, 20, 28, 66, 7, 9.

> The two weightings agree moderately (Spearman ≥ 0.6): the broad winners hold, but individual route priorities do shift with the rider-weighting model.

Passenger-minutes saved: estimated 6,574 vs APC-weighted 5,254.

---
Generated by `scripts/validation_study.py --period midday --volume-mode ridership --time-limit 120 --days 500`.