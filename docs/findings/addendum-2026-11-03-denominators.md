# Addendum — which ghost denominators rest on partially polled days (2026-11-03)

**Status: current. Addendum, not a replacement.** The frozen snapshots are not
edited (they are immutable by rule); read this beside v1, v2, v5, v6, v7 and
v8 and quote the table in §3 rather than their headlines where the two
disagree.

## 1. What changed, and why this audit exists

`ghost_ledger.csv` now records, per service date, the poll window its numbers
were computed from (`poll_first` / `poll_last` / `poll_count` /
`poll_complete`) plus the four columns' provenance rule. Every one of its 78
rows was backfilled from the surviving snapshot files on 2026-11-03
(`ghost_trips.py --backfill-windows`), which turned an invisible property —
*how much of the day was actually polled* — into a column.

**Twelve rows came back `poll_complete=no`.** A ghost rate is
`ghosts / verifiable`, and `verifiable` counts only trips whose scheduled span
contained a poll; on a partially polled day the denominator shrinks while the
same trips still run, so the rate is **biased upward**. These twelve are
therefore not "bad data" — they are days whose rate contribution cannot be
read as service.

| date | window | verifiable | why (from the surviving files) |
|---|---|---:|---|
| 2026-08-17 | 15:00–18:59 | 1,345 of 5,423 | **first collection day** — 3 files, all 15:00–15:43 |
| 2026-08-18 | 08:31–23:57 | 2,318 | collector begins 08:31 (8 files) |
| 2026-08-19 | 07:22–23:59 | 3,763 | 8 files; 06:00 then nothing until 17:17 |
| 2026-08-21 | 00:26–22:08 | 4,527 | 16 files, nothing after 22:08 |
| 2026-08-22 | 11:18–23:59 | 2,415 | 4 files, first at 11:18 |
| 2026-08-29 | 10:27–23:59 | 2,582 | 4 files, first at 10:27 |
| 2026-09-19 | 13:01–23:59 | 2,195 | 4 files, first at 13:01 |
| 2026-09-23 | 00:46–23:59 | 5,497 of 5,589 | 5 files, first at 00:45 |
| 2026-09-24 | 00:08–18:59 | 4,226 | 4 files, nothing after 15:49 |
| 2026-09-25 | 21:47–23:59 | **711** of 5,589 | 2 files — collection almost entirely absent |
| 2026-10-03 | 01:39–18:59 | 1,795 | 4 files, nothing after 15:56 |
| 2026-10-05 | 01:59–23:59 | 4,380 | 8 files, no 00:00 window |

None of these can be repaired by re-derivation: the un-polled hours have no
snapshot files on disk (the raw `vp_*.json` are pruned ~10 weeks out, so the
oldest dates are also the least recoverable).

## 2. Method

For each published window, sum the per-route rows of the live
`ghost_trips.csv` for the window's dates, and repeat with the twelve
lower-bound dates excluded. The second figure is the conservative one: it
drops the days whose contribution is inflated by partial polling. Reproduce
from the data home:

```python
import pandas as pd
csv = pd.read_csv("ghost_trips.csv", dtype={"service_date": str})
led = pd.read_csv("ghost_ledger.csv", dtype={"service_date": str}).set_index("service_date")
lb = set(led[led.poll_complete == "no"].index)
for a, b in [("20260817","20260823"), ("20260824","20260830"), ("20260914","20260920"),
             ("20260921","20260927"), ("20260928","20261004"), ("20261005","20261011")]:
    d = csv[(csv.service_date >= a) & (csv.service_date <= b)]
    ok = d[~d.service_date.isin(lb)]
    print(a, b, int(d.verifiable_trips.sum()), int(d.ghost_count.sum()),
          f"{100*d.ghost_count.sum()/d.verifiable_trips.sum():.3f}%",
          f"{100*ok.ghost_count.sum()/ok.verifiable_trips.sum():.3f}%")
```

## 3. The six windows

| snapshot | published | reproduces from today's artifact? | rate | rate without lower-bound days | verdict |
|---|---|---|---|---|---|
| **v1** Aug 17–23 | 482 of 30,328 (9 days, **1 in 60**) | **No** — the artifact holds 130 of 21,533 | 0.60% (1 in 166) | **0.32% (1 in 312)** | **do not quote any rate.** 5 of 7 days are lower bounds, and the published figure predates both the departure-identity dedup fix and the rows' 2026-10-07 rewrite (`first_run` 2026-09-15, `last_run` 2026-10-07) |
| **v2** Aug 24–30 | 161 of 29,810 (1 in 185) | **Yes** — exact | 0.54% (1 in 185) | 0.55% (1 in 183) | quotable; one lower-bound day (Aug 29, 2,582 trips), sensitivity < 2% |
| **v5** Sep 14–20 | 109 of 29,605 (0.37%, 1 in 272) | **No** — the artifact holds 125 of 32,477 | 0.39% (1 in 260) | 0.38% (1 in 263) | quotable, but cite the current artifact (0.39%), not 109/29,605: those rows were rewritten on 2026-10-07 (`last_run`), so the frozen figure no longer exists in the artifact. One lower-bound day (Sep 19), sensitivity < 2% |
| **v6** Sep 21–27 | 116 of 27,217 (1 in 235) | **Yes** — exact | 0.43% (1 in 235) | **0.39% (1 in 258)** | quotable **with** the lower bound stated: three days are partial (Sep 23–25; Sep 25 was polled only 21:47–23:59). The snapshot's own outage note covers part of this; the number to add is the ex-partial-day rate |
| **v7** Sep 28–Oct 4 | 89 of 22,492 (1 in 253) | **Yes** — exact | 0.40% (1 in 253) | 0.40% (1 in 249) | quotable; one lower-bound day (Oct 3), sensitivity < 2% |
| **v8** Oct 5–11 | 161 of 32,782 (0.49%, 1 in 204) — erratum §4 | **Yes** — exact | 0.49% (1 in 204) | **0.39% (1 in 258)** | quotable **only with** the Oct-5 caveat: that day covers 01:59–23:59 and verifies 4,380 of 5,589, so roughly a fifth of the "corrected" rate is the partial day. The conservative figure is 0.39% |

**The one-line consequence:** the two windows whose rates should not be quoted
as published are **v1** (unreproducible, 5 of 7 days partial) and, in its exact
published number, **v5** (basis rewritten after freezing). v6 and v8 stay
quotable but lose about 9% and 21% of their rate respectively once the partial
days are excluded — which matters because v8's number came from the erratum
whose whole purpose was to remove a denominator distortion.

## 4. Known residual, not corrected here

Some complete-window rows were computed on a **single-date file basis** (5,313
verifiable) where the same files plus the next day verify 5,564 — e.g. Sep 18
reads 5,312 beside 5,564 on Sep 14–17. The gap is the post-midnight trips,
whose polls live in the next day's first window. It is ~0.8% of a week's
denominator and does not change any verdict above, but a future re-derivation
pass should put every date on one footing (D and D+1) and re-cut the affected
weeks rather than mixing bases.

## 5. Limits

* "Why" in §1 is read off the surviving file list, not a collector log for
  those dates; a pruned file and a never-written file look identical to this
  method. The distinction does not change any verdict — both make the day
  partial.
* The lower-bound days cannot be raised by re-derivation: the un-polled hours
  have no snapshots. Only a future collector outage log could say which were
  outages rather than restarts.
* Rates elsewhere in these snapshots (earliness, crowding, headways) are
  untouched by this audit; only the ghost denominator is at issue.

## 6. What is published, and what is not

The dated lines above are published. v5, v6, v7 and v8 each carry the same
"2026-11-03 (dated addendum)" banner in the showcase, and this document is
published beside them (2026-11-04), so every link from a snapshot resolves.
The snapshots' bodies are untouched — a frozen page gains a dated line, never
an edit, which is the rule the [Oct-26 erratum](erratum-2026-10-26-reliability-denominator.md)
followed.

**Why this audit exists at all is a gate defect, not a data one.** The check
that compares these pages against their private twins parses the whole
`obs_lateness*.csv` corpus — 3.5 GB of CSV, ~3.2 GB resident — so it ran past
its own timeout on every nightly, and the chain filed that timeout as
advisory. A check that cannot finish reports nothing, which is why the
denominator lines sat unpromoted after being written. The diagnosis is
recorded privately in `runs/drift-gate-diag-20261103.md`; the corpus-side fix
(per-segment unique counts) and the timeout/verdict fix are both in now.

Three things are still **not** published, and this page does not imply them:

* **v1 and v2 are not part of the showcase's `findings/` set**, so the gate
  has no public twin to diff them against; the lines above for those two
  windows live in the private record only. An earlier draft of that section
  named them as drifting, which was wrong — they cannot drift.
* **The findings index is behind by three windows** — v11, TTC W1 and TTC W2.
  Their pages are not published yet, so the index cannot link them. The rows
  they would carry are the ones whose figures appear nowhere else: v11's
  window holds 3,697 rows for Oct 26 and none for Oct 27 – Nov 1 (a data
  gap, no metric by design), and TTC W2 publishes its Oct 29–31 silent-trip
  rates — 47.5%, then 74.0%, then 83.1% — only with the prohibition that they
  track verification coverage rather than service, alongside an F4 short day
  of 586 polls against a floor of 633. The private index also carries v1's
  0.6% and the window dates `26` / `29` in the same rows. None of it should
  be quoted from this page; it is named here so the lag is visible instead of
  silent.
* **The showcase README's instrument floor** is declared in a registry, not
  derived from the corpus, so it moves on an owner's cadence rather than on a
  refresh; when it lags, the gate says so and this page does not restate it.

The corpus figures here come from the same artifact the published snapshots
were cut from; nothing in sections 1-5 was re-derived to produce this page.
