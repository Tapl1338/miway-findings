# Findings snapshot v2 — second collection week (Aug 24–30)

- **Window:** Aug 24 – Aug 30, 2026 (n = 7 days, all datable)
- **Frozen:** 2026-09-04. This snapshot is immutable; it will never be edited.
  Superseded by: [v3](findings-v3-n7-aug31-sep06.md)
- **Source:** live collector artifacts (`backend/app/data/`) as of 2026-09-04,
  windowed by `backend/scripts/derive_findings.py --start 2026-08-24
  --end 2026-08-30 --source live`. Methods (dedup rule, thresholds, bucket
  definitions) are pinned as constants in that script; regenerate with the
  same command to audit every number below.
- **Status:** PRELIMINARY. Rates from a young baseline (two weeks) will be
  re-estimated each week; see the
  [snapshots index](README.md) for the current version.
- **Civic action:** presented to the Ward 9 Councillor's office in August 2026;
  the office referred the report to MiWay staff for investigation (ongoing).

## Headline findings (n = 7 days, Aug 24–30)

### 1. Night crowding

- Route 2 (Hurontario) late night: averages ~43% full; worst decile at or
  over 100% capacity; ~19.1% standing-room-only or worse (n = 42,307).
  The last bus of the night being crowded remains a rider-safety issue.
- Route 109 (Meadowvale Express) PM rush: ~42% full average, worst decile
  ≥120%, ~15.9% SRO+ (n = 74,940). Route 5 at Dixie: ~37% full, worst decile
  ≥100%, ~10.4% SRO+ (n = 46,173).
- Routes averaging at least a third full after 7 pm (pinned threshold:
  ≥33.3% mean, n ≥ 1,000): **3 routes — 2, 61, 66**. (v1 could not pin this
  count across documents; the pinned method in `derive_findings.py` resolves
  it. The count is sensitive to the threshold; the named routes are the
  stable signal.)

*Method note: occupancy_stats is a collection-wide aggregate with no date
dimension — crowding figures cover the whole collection period to date, not
the window alone. The window-isolated crowding cut requires a re-aggregation
pass (planned for v3).*

### 2. Reliability

- ~1 in 185 verifiable trips never ran at all (161 of 29,810 over 7 days).
  **Compare carefully:** v1's week showed 1-in-34 — the difference tracks
  detector fixes and maturing coverage, not necessarily a service change.
  Week-over-week ghost-rate comparisons are NOT yet meaningful; the
  consistent-window series starts here.
- 26.8% of departures left ≥2 minutes early (n = 1,122,642, fully datable);
  AM peak (07:00–09:00) concentrates it: 36.1% (n = 123,203). Mean lateness
  −0.19 min. An early bus is a missed bus.

### 3. APC sensor audit (field collection, ongoing)

- 367 hand-counted check-ins across 14 routes as of this freeze (v1: 277
  across 12). Counters still cannot distinguish 5 passengers from 12, never
  read below "20% full", and miss load changes in both directions.
- Consequence unchanged: ridership data used for service planning could be
  off by a factor of 2–3× without anyone knowing.

### 4. Transfer timing (model results, labeled separately from measurement)

- Model-derived; see `realized_waits.csv` and the CP-SAT offset solver.
  Unchanged from v1: small re-timings fix specific broken Meadowvale
  pairings, and a network-wide re-time is not a net win for Ward 9 without
  per-stop equity guardrails.

## What changed vs v1 (method, not world)

- First week where every figure derives from the same 7 datable days
  (v1's earliness could only draw on Aug 23; crowding was collection-wide).
- Ghost ledger now includes the departure-identity dedup fix and
  post-midnight correction; v1's frozen ledger predates them, which is why
  its rate differs from the email-era 1-in-60.
- After-7pm route count pinned by an explicit threshold for the first time.

## What changes in v3

- First post-Sept-7 window: scored comparison against the pre-registered
  predictions ([`docs/runs/pre-registration-sept7.md`](pre-registration-sept7.md)).
- Window-isolated crowding aggregation (occupancy_stats currently has no
  date dimension).
