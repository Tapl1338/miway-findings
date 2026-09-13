# Findings snapshot v1 — first 7 collection days

- **Window:** Aug 17 – Aug 23, 2026 (n = 7 days)
- **Frozen:** 2026-09-03. This snapshot is immutable; it will never be edited.
  Superseded by: [v2 — Aug 24–30](findings-v2-n7-aug24-30.md)
- **Source:** collector evidence frozen in
  `docs/runs/evidence-freeze-manifest.md` (private repo),
  truncated to the 7-day window.
- **Status:** PRELIMINARY. Rates from a young baseline (7 days) will be
  re-estimated each week; see the
  [snapshots index](README.md) for the current version.
- **Civic action:** presented to the Ward 9 Councillor's office in August 2026
  (with an early 9-day variant of these figures); the office referred the
  report to MiWay staff for investigation (ongoing).

## Headline findings (n = 7 days)

### 1. Night crowding

- Route 2 (Hurontario) at midnight averages ~40% full; the worst decile runs
  at or over 80% capacity; ~19% standing-room-only or worse (n = 13,787).
  The last bus of the night being crowded is a rider-safety issue, not a
  rush-hour-only problem.
- Route 109 (Meadowvale Express) PM rush: ~41% full average, worst decile ≥60%,
  ~23% SRO+ (n = 23,668). Route 5 at Dixie shows the same shape (n = 14,533).
- Several routes average at least a third full after 7 pm (31, 61, 2, 66, 110).
  *(Count reconciled across documents differs — 5, 6, or 7 depending on
  threshold and window; the named routes are the stable signal. To be pinned
  exactly in v2.)*

### 2. Reliability

- ~1 in 60 verifiable trips never ran at all (482 of 30,328 over nine days;
  7-day rate to be re-derived in v2 — the earlier public 1-in-32 figure was a
  post-midnight counting bug, corrected 2026-08-26).
- 30.0% of recorded departures leave more than two minutes early
  (n = 622,183, nine-day window); AM peak concentrates it: 37% between
  07:00–09:00 (n = 76,134). An early bus is a missed bus.

### 3. APC sensor audit (field collection, Aug 18–21)

- 277 hand-counted check-ins across 12 routes: counters cannot distinguish
  5 passengers from 12, never read below "20% full", report in coarse 20%
  buckets with per-vehicle thresholds, and miss load changes in both
  directions (hysteresis + lag).
- Consequence: ridership data used for service planning could be off by a
  factor of 2–3× without anyone knowing. Three specific vehicles account for
  most observed failures and are the proposed audit starting point.

### 4. Transfer timing (model results, labeled separately from measurement)

- Shifting a few departures by 3–5 minutes fixes specific broken Meadowvale
  pairings with no new buses or service hours.
- A network-wide re-time is NOT a net win for Ward 9 as-is (15 of 21 ward
  stops get worse in the all-day model), so no endorsement is requested
  without per-stop equity guardrails.

## What changes in v2

- 7-day rates re-derived on the consistent window (nightly crowding shares,
  missed-trip rate on the same n as everything else).
- The after-7pm route count pinned to an exact threshold.
- First scored comparison against the pre-registered Sept-7 predictions
  ([`docs/runs/pre-registration-sept7.md`](pre-registration-sept7.md)).
