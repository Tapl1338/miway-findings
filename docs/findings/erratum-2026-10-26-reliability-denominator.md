# Erratum — the October reliability denominator (2026-10-26)

**Status: current. Addendum, not a replacement.** Findings v8, v9 and v10 each
say in their §0 *"the reliability denominator is broken — do not quote the
ghost rate."* That instruction was correct when it was written and is
withdrawn here, for those three windows only, because the artifact has been
repaired and the rates re-derived. The frozen snapshots are not edited (they
are immutable by rule); read this erratum **beside** v8 §0.2, v9 §0 and
v10 §0.4, and quote the table below rather than either of theirs.

Artifacts: `ghost_trips.csv` / `ghost_ledger.csv` / `ghost_trips.md` in the
collection data home, repaired 2026-10-26 with `ghost_trips.py` at the commit
that adds `MIN_FRESH_COVERAGE_FRACTION` + `report_rows_from_frame`.

## 1. What was wrong

`ghost_trips.csv` held, for October weekdays, a *verifiable* denominator of
**303** trips where the schedule carries **5,589** and a healthy run verifies
~5,500. The same three constants — **303 / 200 / 100** — recurred across
dates, which is the tell: a constant ~4.5 verifiable trips per route is not a
service signature, it is a computation signature.

Reproduced on 2026-10-26: loading **all** of 2026-10-07's snapshot files
gives 5,313 verifiable trips for Oct 7; the same code loading only Oct 6's
`00:01–00:50` midnight tail gives **exactly 303 for Oct 6**. A date seen only
through a neighbouring day's edge sliver always lands on one of those three
numbers.

**The collector was not the cause.** Every October day holds ~2,460–2,500
polls spanning a full 24 h with 0–9 poll failures in the coverage artifacts,
i.e. the VPS was healthy throughout (see §5 for the second, separate reason a
date could also look thin).

## 2. Why it was permanent

`ghost_trips.py --since` (the daily chain's cursor) skips every service date
at or before the cursor's date — a deliberate 2026-10-12 change that stopped a
6.6 GB full scan from `MemoryError`-ing the chain. So a date is recomputed
**once**, by the run that first sees it. The run that first saw those dates
held polls for a sliver of each day, wrote ~303 verifiable trips, and the
cursor then stepped past them forever. Nothing downstream re-examined the
number; the weekly snapshots quoted whatever was in the file.

## 3. The fix (two parts)

1. **A coverage guard** (`_coverage_collapsed`, `MIN_FRESH_COVERAGE_FRACTION =
   1.0`). A recompute may only replace a stored date's rows when it verified
   at least as many trips as the stored row did — 1.0, not a percentage,
   because a later pass reads the *same or fewer* poll files (raw `vp_*.json`
   are pruned ~10 weeks), so its base can shrink from lost coverage and never
   from lost service. The guard is applied per **service date** (a partial
   pass is a property of the run, not of a route) to both the CSV and the
   ledger, and it stands down when `scheduled_trips` itself collapsed (a feed
   vintage change, not a lost poll). 8 unit tests.
   Why 1.0 and not 0.5 — measured during the repair: a 50% threshold let a
   **94%** pass through and quietly shrank Oct 5 from 4,380 to 4,129.
2. **The report follows the file** (`report_rows_from_frame`). The `.md`
   used to be built from the run's fresh rows while the CSV was merged, so a
   protected date read 3,224 in the CSV and 200 in the report from the same
   run. The report is what a reader quotes.

## 4. The re-measure, and what it changed

Backfill: every date from Oct 5 to Oct 25 recomputed from its own snapshot
files **plus the neighbouring days' files**, because a poll after midnight
carries the *previous* service date — a day's late trips can only be verified
by the next day's first file. Single-date runs therefore undercount by ~4%:

| basis | weekday verifiable | share of 5,589 |
|---|---|---|
| single-date pass (the Oct 27 backfill's first shape) | 5,313 | 95.1% |
| date + one neighbour day each side | **5,564** | **99.6%** |

Both shapes were run; the file now holds the second for every date Oct 5–25,
so the windows below are measured on one basis. Saturdays land at
3,431/3,431 and Sundays at 2,715/2,716, except **Oct 5 (4,380 / 78.4%)**,
whose raw snapshots are pruned by retention — that row keeps the richer
number the guard protects, and it is the one date in the windows whose
denominator is still a floor rather than a measurement.

### Corrected reliability, quotable

| window | scheduled | verifiable (share) | ghosts | rate | 1 in |
|---|---|---|---|---|---|
| v8 — Oct 5–11 | 34,092 | 32,782 (96.2%) | 161 | **0.49%** | 204 |
| v9 — Oct 12–18 | 31,219 | 31,117 (99.7%) | 93 | **0.30%** | 335 |
| v10 — Oct 19–25 | 34,092 | 33,916 (99.5%) | 179 | **0.53%** | 189 |

Pre-damage band for comparison: v5 0.37% (1 in 272), v6 0.43% (1 in 235),
v7 0.40% (1 in 253) — `docs/findings/findings-v{5,6,7}-*.md` §scorecards.

**Verdict.** All three repaired windows sit inside the 0.30–0.53% band the
pipeline produced before the damage: no reliability regime change, no
October regression, and **no improvement** — v10 at 0.53% (1 in 189) is the
thinnest week of the three and the arithmetic is now trustworthy enough to say
so. The v8 note's "1 in 113 is not an improvement" reading was right about the
conclusion and wrong about the cause: 161 ghosts over 32,782 verifiable trips
is 1 in 204, ordinary.

**Concentration is unchanged and still real:** the ghosts cluster on route 11
(37 over three weeks), 110 (29), 126 (22, 2.24% of its own base), 39 (22),
22 (18), 74 (17, 3.80%), 44 (17), 49 (17, 2.35%). Route 25 — which v10 §0.4
reported as *absent from the ghost ledger entirely while 205,031 observation
rows existed* — is present for every date after the repair, with 21 scheduled
and 21 verifiable per weekday. Its absence was the same write-time artifact,
not a missing route.

## 5. Residual caveats (do not over-read the table)

- **Oct 5 is a floor.** Its raw snapshots are pruned, so 4,380 is what the
  richest pass still held; the true figure was probably ~5,560 like its
  neighbouring weekdays. Its 51 ghosts over the smaller base is the one
  figure in v8 that remains inflated (1.16% against a ~0.9% true rate).
- **The 303-class rows are now unreproducible on purpose.** If a future run
  prints "kept the stored rows for N date(s) whose recompute verified <100% of
  their base", that is the guard working, not a new failure — the run saw less
  of the day than the stored row did.
- **Retention sets a floor at ~10 weeks.** Any date older than the raw-snapshot
  horizon can never be re-measured upward, only protected. The window between
  the collection and the freeze is when a denominator can still be repaired;
  freeze *before* the raw cut is pruned.
- **`ghost_trips.md` poll-window labels** read like `23:42–00:51` for a
  service date. That is the honest span of that service day's polls (the
  vendor stamps early-morning trips with the previous service date), not a
  clock error — but read the poll **count**, not the label, when judging
  coverage.
