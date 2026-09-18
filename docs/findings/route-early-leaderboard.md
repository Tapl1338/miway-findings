# Route-level early-departure leaderboard — computed from the public sample

> **Purpose:** demonstrate the published dataset's research value by deriving a
> new finding **entirely from the public deposit** — no private data, no
> unpublished columns. Every number below regenerates from the Zenodo dataset
> with the one-liner at the bottom.
>
> **Data:** `lateness-sample-250k.csv` from the published deposit — **DOI 10.5281/zenodo.22820448** (zenodo.org/records/22820449); seed-pinned sample of
> the observed-lateness corpus, Aug 23 – Sep 15, 2026, n = 250,000).
> **Definition:** "early" = `lateness_minutes < -2` (departed ≥2 min ahead of
> schedule — fails even the loosest on-time window; an early bus is a missed
> bus for a timetable rider).
> **Status:** derived from the frozen public sample only; future re-cuts
> (v1.1.0+) will shift these numbers slightly — cite with the dataset version.

## The finding

Early departures are not uniform across the network — the worst high-volume
routes run **3–4× the early-departure rate of the best**, on samples of
thousands of observations each:

| Rank (worst) | Route | n | Early-departure share |
|---|---|---|---|
| 1 | 51 | 5,615 | **40.8%** |
| 2 | 5 | 8,306 | **40.7%** |
| 3 | 101 | 2,955 | **38.9%** |
| 4 | 45 | 5,724 | 35.6% |
| 5 | 18 | 2,601 | 32.8% |
| 6 | 39 | 9,006 | 31.7% |
| 7 | 38 | 7,126 | 31.5% |
| 8 | 103 | 2,419 | 30.6% |
| … | network all-day | 250,000 | 24.7% (61,663 early departures) |
| best (n≥1,000) | 14 | 1,564 | **9.6%** |
| best | 22 | 1,676 | 12.2% |
| best | 11 | 3,343 | 14.4% |

**Reading:** route 51 leaves ≥2 min early on **2 of every 5 departures** —
more than four times route 14's rate. This is a *schedule-design* signature,
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
