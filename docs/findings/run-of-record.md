> **Provenance:** the private repo's frozen run-of-record (`RUN-OF-RECORD.md`), promoted verbatim; verified token-for-token on every push. It documents the project's discipline: canonical regeneration commands, frozen numbers, determinism notes, and every errata — including the self-caught detector bug that moved the headline ghost rate from 1-in-32 to 1-in-63 — kept as evidence of how the measurement evolved.

# FROZEN RUN OF RECORD — pre-Sept-7 baseline

**2026-08-24.** All councillor-facing documents quote THE NUMBERS BELOW and
nothing else until the post–Sept 7 re-run replaces them.

## Canonical regeneration commands (backend/, in this order)

```bash
python scripts/exec_summary.py  --period all_day --volume-mode ridership \
    --max-shift 5 --buffer 2 --time-limit 120 --max-connections 6000
python scripts/equity_report.py --period all_day --volume-mode ridership \
    --max-shift 5 --buffer 2 --time-limit 120 --max-connections 6000 \
    --ward-csv app/data/ward_stops.csv
```

`--max-connections 6000` is NOT optional: without it the solver takes every
connection, lands on a much weaker FEASIBLE solution, and every downstream
number shifts (a ~3,400/day brief briefly circulated from exactly this).


> **Basis (DEC-04, acked by referee 2026-08-24):** unified `--time-limit 120` on BOTH canonical generators; `--service-date 20260805 --expect-basis pre` (26AU03 block); JSONs carry T14 params+fingerprint stamps; realized-latency Monte Carlo: 338,667 departures, wins 100% of 500 days, median +785 net min/day.

## Frozen values (from docs/exec-summary.json + docs/equity-report.json)

| Metric | Value |
|---|---|
| Network passenger-minutes saved | **9,737.7/day (~9,700)** (unified --time-limit 120, post phantom-filter model) |
| Weighted avg transfer wait | 18.84 -> 16.82 min |
| Missed connections | 2,789 -> 2,456 |
| Passenger-minutes of waiting | 90,827.0 -> 81,089.3 |
| Lateness sensitivity (1/2/3 min mean) | +4,280 / +2,867 / +1,862 saved |
| Ridership projection | +1.94%/day (~4,106/day, band 800-22,100); farebox $3.43M ($0.69-18.5M) |
| Ward 9 | 6 of 21 stops better off; **+2.56 min avg** (worse); rider proxy ~215,600 | [DEC-07: corrected from "10 of 21" — transcription slip; equity-report.json:503-507 says worse_off=15, ahead=6] |

Solver runs are FEASIBLE (time-limited), so reruns drift a few percent at the
network level and more at ward level. That is WHY this file exists: when the
numbers move, regenerate here first, update this table second, sync prose
third — never let prose chase a stray run.

Post-Sept 7: capture the new feed (`gtfs_archive/MANIFEST.md`), then rerun
both commands against it and open a NEW section below rather than editing
these rows.


## Determinism notes (2026-08-23 forensic pass)

- **Transfer graph build is deterministic**: two identical-config canonical
  runs today both produced nodes_analyzed=237 on the unchanged Aug 19 feed
  (all gtfs/*.txt mtimes 2026-08-19; cache manifest fingerprint matches).
- **The solver endpoint is not**: CP-SAT under a wall-clock time limit reports
  whichever FEASIBLE solution it has reached. Four identical-config reruns
  today produced 4,534 / 4,140 / 4,107 / 4,117 saved (-9% to +7% around the
  mean). Network claims must quote the range or the conservative end;
  ward-level deltas wobble more (+2.35 vs +4.47 for Ward 9 across draws)
  while the direction (ward nets worse; network saves ~10%) never flipped.
- If bit-exact reproducibility is ever needed: pin num_search_workers=1 and a
  fixed random_seed in solve_transfer_sync (accepts longer runtimes).
- Kill any running uvicorn instance before official reruns -- its warmup
  threads share the same disk cache directory as script runs.


## Post-filter basis clarification (added Sunday night)

Two consistent artifact sets exist and BOTH are valid:

- COMMITTED (pre-filter graph, 237 nodes, 15 W9 stops, +2.35 min,
  saved 4,140): matches docs/drafts/email-B-story.txt as-is.
- DISK (post-filter graph, 258 nodes, 21 W9 stops, +2.60 min,
  saved 3,394): what any fresh regeneration produces.

Tuesday rule: pick ONE track and ship it whole. Sending the static
email-B-story.txt = zero moving parts (stamp: data through Aug 23).
Regenerating instead = fresher counts AND the 21-stop Ward 9 line -
expected, do not hand-revert it. Never mix rows from both sets in one
document.


## Provenance (appended 2026-08-24 by alpha-3 -- metadata only, no numbers)

* The frozen solves above ran on representative date **20260805**
  (service block **26AU03**, pre-Sept-7), resolved by the mode-count +
  earliest-tiebreak heuristic -- verified 2026-08-23 (REDFLAG S12).
* Canonical/rerun commands must now pin this explicitly:
  `--service-date 20260805 --expect-basis pre` on exec_summary.py and
  equity_report.py (T13). Omitting them re-enables the heuristic, which
  flips to block 26SE07 as soon as August dates leave the feed.
* Post-Sept-7 rerun: pass `--service-date <picked> --expect-basis post`
  and record the literal date + active service_id set here.


## Errata: councillor email sent 2026-08-25 (DEC-09)

Two number corrections to carry into any follow-up or meeting materials.
Both understate the case; neither warrants a correction email on its own.

1. **Ward 9 early departures.** Email says Ward 9 stops run "slightly
   worse than the city as a whole: 30.0% vs 30.5%". The direction is
   flipped: 30.0% < 30.5% means Ward 9 is slightly BETTER than the city
   average (fewer early departures). Alpha-6 flagged this sign-flip in
   the pre-send falsifier pass; it survived regeneration.
2. **Meadowvale terminal waits.** Email says "average waits at the
   terminal hold near eight minutes". Canonical artifact says ~14 min:
   departure-weighted 13.5 scheduled -> 14.1 realized min
   (realized_waits.csv/.md, 2026-08-18 AU basis). Use fourteen, not
   eight.

Everything else in the sent email verified against artifacts per alpha-6's
EMAIL-FALSIFY pass (STATUS row 2026-08-25T01:20Z) and the DEC-06 ruling.
3. **Ghost-trip count — telemetry caveat (T44 Layer 1, alpha-6).**
   The "687 of 23,297 verifiable trips never ran" statistic is robust for
   the subset inside healthy-coverage route-days (305 of 866 frozen-cut
   ghosts occurred where the same feed tracked >=80% of sibling trips —
   docs/runs/T44-telemetry-layer1.md), but 65% of ghosts fall in
   lower-coverage route-days where a dead-AVL explanation cannot yet be
   excluded. **Hedge sentence for any re-quoting:** "Of the missed trips
   we can digitally verify, one-third occurred on routes and days where
   the live feed was otherwise tracking more than four of every five
   scheduled buses; the remainder await on-street confirmation." Field
   confirmation protocol: docs/runs/T44-field-protocol.md (execution: field team). Do not quote updated totals from the frozen cut — different
   vintage than the sent basis.


### Errata addition (2026-08-25T20:15Z): ghost statistic CORRECTED - detector bug found and fixed

The sent email's reliability claim ('866 of 28,079 verifiable trips (3.1%),
roughly one in 32') was OVERSTATED due to a detector bug (REDFLAG
2026-08-25): MiWay's feed stamps each bus record with the wall-clock date,
so every post-midnight trip was unmatchable and auto-flagged. Fixed by
time-windowed matching (commit dabb95d); regression test locked.

CORRECTED BASIS (all collected days through Aug 25):
482 of 30,328 verifiable trips = 1.59 percent - roughly ONE IN 63.
Late-night false flags drop from 665 to 9. Genuine daytime ghost routes
now visible: 22 (30), 61 (25), 66 (24), 74 (24), 2 (18), 35 (16) across
the collection window.

USE IN ANY FOLLOW-UP: 'a correction to my first note - after fixing an
error in my own tracking tool, the missed-trip figure is about one in 60
verifiable trips, not one in 32. I would rather catch my own mistake than
have it caught for me.' (Self-correction framed as credibility asset.)

### Errata addition (2026-08-25T21:1xZ): canonical evidence freeze RESTORED (DEC-11A/T47)

The pre-Sept-7 observed-basis freeze at docs/runs/evidence-freeze-pre-sept7/
was re-canonicalized to the alpha-7 215d1d9 lineage after the def19fb
replacement proved unverifiable (REDFLAG F1, D-12). Single manifest:
docs/runs/evidence-freeze-manifest.md. All six archives independently
decompress-rehash verified against it. Note for consumers: obs_lateness.csv
is NOT append-only - a collector rewrite pass shrank it by 14,654 rows
post-freeze (D-12 F2); row-set comparisons, not byte diffs, are the
correct drift audit against this file.

### Ruling (2026-09-11): DEC-13 — dated versions, never in-place edits, for number-bearing documents

Any document that publishes numbers for quoting (findings, briefs, T-task
rollups) is NEVER edited in place after publication. Corrections, errata,
and later-era restatements are published as a new dated version
(`<name>.v2_<YYYY-MM-DD>.md`) that links back to its predecessor; the
drift BETWEEN versions is retained as evidence of how the measurement
evolved. Receipts in docs/runs/ record why each new version exists.
Applies to every number-bearing document from here on.
First application: docs/rider-hours.v2_2026-09-11.md (errata + current-era
addendum from the T45 falsifier pass, docs/runs/T45-falsifier-20260911.md;
v1 docs/rider-hours.md stays untouched).
