# Findings snapshot v3 — third collection week (Aug 31 – Sep 6)

- **Window:** Aug 31 – Sep 6, 2026 (n = 7 days, all datable). **Sept 7 itself
  is excluded** — it already runs the new (26SE07) schedule and belongs to
  the post-change side.
- **Frozen:** 2026-09-07. This snapshot is immutable; it will never be edited.
  Superseded by: (none yet — [v4](findings-v4-post-sept7-DRAFT.md) is the
  post-Sept-7 skeleton, pending its first full weekday)
- **Source:** live collector artifacts (`backend/app/data/`, frozen at the
  2026-09-07 12:33 data-home cutover — see KNOWN-TRUTHS "Data home") as of
  2026-09-07, windowed by `backend/scripts/derive_findings.py --start
  2026-08-31 --end 2026-09-06 --source live`. Methods (dedup rule,
  thresholds, bucket definitions) are pinned as constants in that script;
  regenerate with the same command to audit every number below.
- **Status:** PRELIMINARY. Third week of a young baseline; see the
  [snapshots index](README.md) for the current version.
- **Civic action:** presented to the Ward 9 Councillor's office in August
  2026; the office referred the report to MiWay staff for investigation
  (ongoing).

## Week context (context_calendar.csv)

- **Aug 31:** heavy rain (11.0 mm). **Sep 2:** the heaviest precipitation of
  the collection (16.6 mm thunderstorm) — also a PA day on both boards
  (staff only). **Sep 3:** collector duplicate-row incident (dedup applied;
  see the incident notes) — also PA day. **Sep 5–6:** weekend (lower volume,
  normal shape). No holiday markings in the window.
- Daily dated-row volumes: 191,952 / 194,627 / 203,598 / 203,390 / 203,968 /
  134,747 / 101,173 — weekday volumes flat, weekend dip normal. The Sep 2
  storm and Sep 3 incident did **not** dent row coverage.

## Headline findings (n = 7 days, Aug 31 – Sep 6)

### 1. Reliability

- **1 in 118 verifiable trips never ran at all** (277 of 32,566 over 7
  days). Week series so far: v1 1-in-34 → v2 1-in-185 → v3 1-in-118. The
  week-over-week spread tracks detector fixes and maturing coverage, not
  necessarily service changes; the consistent-window series is still young.
- Worst routes this week: 66 (55 ghosts), 61 (30), 5 (19), 103 (18), 2 (14).
- **25.6% of departures left ≥2 minutes early** (n = 1,227,683 dated rows);
  mean lateness −0.15 min. AM peak (07:00–09:00) concentrates it:
  **33.7% early** (n = 135,571). v2: 26.8% / 36.1% — the early-departure
  pathology is stable week over week.
- **Method correction (2026-09-07 claim audit, same hour as freeze):** the
  figures above use the freshest-horizon dedup, which leaves ~115k rows
  whose freshest record is still a FORECAST (departures never observed
  measured — largely ghosts and window-edge rows) in the denominator. Under
  the canonical FQ-10 rule (measured rows only, horizon ≤ 0 — the repo's
  locked early-share recipe): **26.3% early (n = 1,112,634), AM peak 34.9%
  (n = 129,276)**. The FQ-10 numbers are canonical going forward; both
  methods tell the same story (stable ~26% pathology), and the 0.7pp gap is
  within the FQ-10 restate trigger's 1pp tolerance — recorded here rather
  than silently re-quoted. v2's figures carry the same method caveat; do
  not compare across the two bases without noting it.
- An early bus is a missed bus (MiWay's on-time window is −1/+5; every early
  departure counted here misses both windows).

### 2. Night crowding (raw APC signal, uncorrected)

- Route 2 (Hurontario) late night: mean **44% full**; worst decile ≥ **100%**
  of capacity (the ≥340% tail rows are the known APC bucket artifact —
  articulated buses whose buckets are relative to a smaller reference —
  treated as an upper bound, not a load); **19.7% standing-room-only or
  worse** (n = 50,101). The last bus of the night being crowded remains a
  rider-safety issue.
- Route 109 (Meadowvale Express) PM rush: mean **41% full**, worst decile
  ≥ **80%**, **15.7% SRO+** (n = 81,555). Route 5 at Dixie (PM rush): mean
  **37% full**, worst decile ≥ **100%**, **10.0% SRO+** (n = 49,358).
- Routes averaging ≥33% full after 7 pm (pinned threshold: ≥33.3% mean,
  n ≥ 1,000): **3 routes — 2, 66, 61** (same trio as v2).

*Method note (unchanged from v2): occupancy_stats is a collection-wide
aggregate with no date dimension — crowding figures cover the whole
collection period to date, not the window alone. The window-isolated
crowding re-aggregation pass remains planned, not built.*

### 3. APC sensor audit (field collection, ongoing)

- Hand-counted check-ins: **367 across 14 routes** (unchanged from v2 — no
  new rides this week). Counters still cannot distinguish 5 passengers from
  12, never read below "20% full", and miss load changes in both directions.
- Consequence unchanged: ridership data used for service planning could be
  off by a factor of 2–3× without anyone knowing. The falling-edge
  stickiness finding (KNOWN-TRUTHS, 2026-08-31) also stands.

### 4. Transfer timing (model results, labeled separately from measurement)

- Model-derived; see `realized_waits.csv` and the CP-SAT offset solver. Not
  recomputed for this snapshot — the model reruns are separate scripts.
- New this week, in the measured half: the night pulse audit
  (`pulse_miss_detector.py`) found timed night connections missing at
  8–33% across six audited terminal pulses (worst: 2→66 at City Centre),
  driven by outbound partners holding +3–7 min past the pulse minute.

## Where this leaves the pre-change record

This is the **last full pre-change week**: the 26SE07 schedule took effect
Sept 7. v4 (post-change) will be the first snapshot where week-over-week
comparisons test whether the service change moved any of these numbers —
ghost rate, earliness share, night crowding, and the night-pulse miss rates
are the four pre-registered comparisons.
