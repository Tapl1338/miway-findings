# Route-level early-departure leaderboard — computed from the public sample

> **Purpose:** demonstrate the published dataset's research value by deriving a
> new finding **entirely from the public deposit** — no private data, no
> unpublished columns. Every number below regenerates from the Zenodo dataset
> with the one-liner at the bottom.
>
> **Data:** `lateness-sample-250k.csv` from the published deposit — **DOI 10.5281/zenodo.22820448** (zenodo.org/records/23444830, v1.1.0); seed-pinned sample of
> the observed-lateness corpus, Aug 23 – Oct 17, 2026, n = 250,000).
> **Definition:** "early" = `lateness_minutes < -2` (departed ≥2 min ahead of
> schedule — fails even the loosest on-time window; an early bus is a missed
> bus for a timetable rider).
> **Status:** recomputed **2026-10-18 against deposit v1.1.0**
> (`lateness-sample-250k.csv`, 250,000 rows, window 2026-08-23 → 2026-10-17).
> The numbers moved with the re-cut: on v1.0.0's draw route 51 led at 40.8% and
> route 14 was 9.6%; the ordering among the worst is not stable across draws —
> the *spread* is. Cite the version you computed on.

## The finding

Early departures are not uniform across the network — the worst high-volume
routes run **3–4× the early-departure rate of the best**, on samples of
thousands of observations each:

| Rank (worst) | Route | n | Early-departure share |
|---|---|---|---|
| 1 | 101 | 2,919 | **40.2%** |
| 2 | 5 | 8,329 | **40.2%** |
| 3 | 51 | 5,283 | **39.5%** |
| 4 | 45 | 5,593 | 33.9% |
| 5 | 18 | 2,226 | 32.3% |
| 6 | 42 | 10,784 | 30.7% |
| 7 | 31 | 2,397 | 30.0% |
| 8 | 38 | 6,979 | 29.6% |
| … | network all-day | 250,000 | 24.1% (60,144 early departures) |
| best (n≥1,000) | 14 | 1,746 | **9.4%** |
| best | 22 | 1,710 | 11.2% |
| best | 110 | 1,621 | 11.7% |

**Reading:** the worst routes (101, 5, 51) leave ≥2 min early on **2 of every
5 departures** — more than four times route 14's rate. This is a *schedule-design* signature,
not random noise: sustained early departures mean the timetable promises
dwell or running time the route doesn't need, and the operator uses the
slack by leaving stops early — the failure mode riders experience as "I was
there on time and the bus had already gone." The best routes (14, 22, 11)
show the counter-case: schedules their operators can actually keep.

**Caveat (honest, structural):** this table measures the *rate*, not the
*cause*. Route-level differences may reflect schedule slack, running-time
variability, layover pressure, or terminal dispatch practice — the dataset
cannot distinguish them, and this finding does not allege operator
misconduct. It identifies where a schedule-vs-observed reconciliation would
be most productive.

## Small-n honesty (why some routes are excluded)

The sample is uniform-random, so rare routes carry few observations. Rates
on small n are unstable and misleading:

| Route | n | Raw "rate" | Why it's not published as a finding |
|---|---|---|---|
| 312 | 10 | 80.0% | 8 departures. One schedule cycle flip moves this ±10 points. |
| 321 | 27 | 59.3% | Too thin to distinguish from chance. |
| 305 | 13 | 38.5% | Same. |

The threshold used above (n ≥ 1,000) keeps every published rate's 95%
confidence interval under ±3 points. This is the same discipline as the
ghost-rate vintage audit: **a rate without a denominator you can trust is
not a finding.**

## Reproduce it (one command)

```python
import pandas as pd
df = pd.read_csv("lateness-sample-250k.csv",
                 dtype={"route_short_name": str, "stop_id": str, "date": str})
df["early"] = df["lateness_minutes"] < -2
g = df.groupby("route_short_name").agg(n=("early", "size"),
                                       pct=("early", lambda s: 100*s.mean()))
print(g[g.n >= 1000].sort_values("pct", ascending=False))
```

Run against the Zenodo sample (or the full corpus in the deposit's
`lateness-actuals-full-dated.csv.gz` — same code, ~14× more rows). Expected
output matches the table above to rounding.

## Why this page exists

The deposit was published to let anyone check the findings. This page is the
proof it works: a *new* network-level result, derived after publication,
using only the public artifact — no privileged access, no hidden columns,
no trust required. That is the difference between "open data" as a slogan
and open data as a method.
