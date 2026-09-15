# Findings snapshot v4 — first post-change week (Sept 7 – 13)

> **Version:** 4 — the first post-change week (Sept 7–13, 2026), frozen
> 2026-09-14 · **Data:** SHA-256 evidence freeze (6 collector
> artifacts, hashes on file in the private repo's evidence manifest),
> regenerated with the pinned pipeline quoted in the header · Full
> receipts — evidence manifest, ghost scoring, derivation log — are
> private-repo artifacts (SHAs on file).


- **Window:** Sept 7 – 13, 2026 (n = 7 days, all COMPLETE — including the
  cutover day Sept 8: the laptop collector carried the day to ~20:15, the
  scp seed merged its rows, and the VPS collector resumed 20:33; the
  handoff gap is invisible in the hourly distribution, which matches the
  Sept 9 control within 1%). **Errata 2026-09-14:** an initial
  over-conservative PARTIAL stamp on Sept 7–8 was corrected pre-publication
  after the hourly check; see the post-sept7 manifest heading.
- **Frozen:** 2026-09-14T22:08:29Z. This snapshot is immutable; it will
  never be edited. Superseded by: (none yet)
- **Source:** the SHA-256 evidence freeze (6 artifacts), windowed
  by the pinned pipeline `derive_findings.py --start 2026-09-07 --end
  2026-09-13 --source freeze` — the first snapshot derived from a freeze
  via the pinned pipeline. Ghost scoring over 48 collection-window files
  (Sept 7–13, ledger upserted) and the derivation log are private-repo
  receipts (SHAs on file). Methods pinned as constants in the scripts;
  regenerate to audit every number below.
- **Status:** CURRENT. First post-change week; the week-over-week
  comparisons against v3 below are the pre-registered ones.
- **Civic action:** presented to the Ward 9 Councillor's office in August
  2026; referred to MiWay staff for investigation (ongoing). The pre-registered
  Sept-7 scorecard ([pre-registration](../pre-registration-sept7.md)) is scored
  separately on ≥10 complete weekdays — this week supplies 5 of them
  (Sept 8–12; 9–10 by the runbook date).

## Week context

- The 26SE07 schedule took effect Sept 7 (service changeover; school trips
  resume). This is the first week where school is IN on the new schedule —
  the trip-level school-flag analysis
  ([school-wave-crowding-v2](school-wave-crowding-v2.md)) covers
  the crowding side; this snapshot holds the network headline rates.
- Daily dated-row volumes: 102,683 / 188,657 / 204,639 / 204,230 / 204,664 /
  135,954 / 105,699 (the Sept 7 figure is the changeover Sunday's own
  lower volume, not a gap; weekend dip normal).
- Known artifact carried in the freeze: 320,857 pre-Aug-23 rows with empty
  date field (legacy era; excluded by day filtering, documented in the
  manifest).

## Headline findings (n = 7 days, Sept 7 – 13)

### 1. Reliability

- **1 in 255 verifiable trips never ran at all** (121 of 30,848 over 7
  days). Week series: v2 1-in-185 → v3 1-in-118 → **v4 1-in-255** (the
  consistent 7-day basis starts at v2; v1's nine-day corrected figure was
  1-in-60, its pre-correction 7-day read 1-in-34). The pre-registered
  prediction (missed-share improves on the new schedule) is on track —
  but the series still tracks detector maturity too, so the scorecard
  verdict waits for the ≥10-weekday cut.
- Worst routes this week: 11 (15 ghosts), 66 (12), 42 (11), 103 (10),
  23 (8), 13 (7), 2 (7). Route 61 — v3's worst at 30 — drops to 2.
- **22.5% of departures left ≥2 minutes early** (n = 1,064,110 measured
  rows, FQ-10 canonical dedup: freshest horizon ≤ 0 per departure); mean
  lateness +0.16 min. AM peak (07:00–09:00): **26.4% early** (n = 113,929).
- **Week-over-week, on the canonical basis: 26.3% (v3) → 22.5% (v4)** —
  the early-departure pathology improved by 3.8pp in the first post-change
  week. This is the headline the pre-registration hoped to test; the
  scorecard applies the drift bands (schedule vs school-vs-traffic vs
  residual) before claiming the retime caused it. The trip-level school-stop
  cut (62% → 39% at school stops, 2.5× the no-school control) is already
  published separately and is consistent with a real schedule effect.
- v3's method caveat applies here in reverse: v4 is quoted on FQ-10
  canonical only. The freshest-horizon-all-rows basis gives 21.2%
  (n = 1,146,526) — 1.3pp below canonical, same story. Do not mix bases
  across snapshots without noting it.

### 2. Night crowding (raw APC signal, uncorrected)

- Route 2 (Hurontario) late night: mean **49% full**; worst decile ≥
  **900%** raw (the ≥340% tail rows are the known APC bucket artifact —
  articulated reference-size mismatch; treat as an upper bound, not a
  load); **21.7% standing-room-only or worse** (n = 24,912). v3: 44% mean,
  19.7% SRO+ — night crowding on the corridor did **not** improve with the
  schedule change.
- Route 109 (Meadowvale Express) PM rush: mean **44% full**, worst decile
  raw ≥ 640% (same artifact), **19.4% SRO+** (n = 38,272). v3: 41% / 15.7%
  — worse, not better.
- Route 5 at Dixie (PM rush): mean **34% full**, **7.9% SRO+** (n = 24,915).
- Routes averaging ≥33% full after 7 pm (pinned threshold: ≥33.3% mean,
  n ≥ 1,000): **10 routes — 6, 2, 126, 16, 101, 110, 11, 1, 35, 109**.
  v2/v3: 3 routes. The count more than tripled; note the occupancy_stats
  artifact is collection-wide (no date dimension) so this absorbs the
  September school-trip restoration — the school-wave analysis attributes
  the increase, and it is the strongest quantitative case yet for the
  evening-service ask in the councillor brief.

*Method note (unchanged): occupancy_stats is a collection-wide aggregate —
crowding figures cover the whole collection period to date, not the window
alone. The window-isolated crowding re-aggregation pass remains planned.*

### 3. APC sensor audit (field collection)

- Hand-counted check-ins: **367 across 14 routes** (unchanged — no new
  rides this week). The threshold-bracket analysis
  ([apc-threshold-brackets](apc-threshold-brackets.md)) and per-vehicle
  bias table stand. Sensor-honesty finding unchanged: displays cannot
  distinguish 5 passengers from 12 and never read below "20% full".

### 4. Transfer timing (model results, labeled separately)

- Model-derived; see `realized_waits` in the freeze and the CP-SAT offset
  solver. Not recomputed for this snapshot — the post-change retime moved
  specific pairings, and the sept7_after 2×2 decomposition (schedule vs
  operations effect) is the scorecard's cell-A/cell-C receipt, due with the
  ≥10-weekday cut.

## What changed vs v3 (pre-registered comparisons, first look)

| Comparison | v3 (pre-change) | v4 (post-change) | First read |
|---|---|---|---|
| Ghost rate | 1 in 118 | **1 in 255** | improved (scorecard confirms) |
| Early share (canonical) | 26.3% | **22.5%** | improved 3.8pp |
| AM-peak early share | 34.9% | **26.4%** | improved 8.5pp |
| Night crowding (Rte 2 SRO+) | 19.7% | **21.7%** | not improved |
| After-7pm ≥33% routes | 3 | **10** | school effect; see wave analysis |

The reliability and earliness improvements are real measured deltas on the
frozen cut; attribution (schedule vs demand) is exactly what the Sept-22
scorecard runbook decomposes. The crowding non-improvement on Route 2
nights strengthens the evening-service ask: the retime helped the timetable
and did nothing for the last bus's load.
