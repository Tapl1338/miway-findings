> **Provenance:** published 2026-10-04 from the platform repository, where this manifest is maintained. It pins the frozen evidence snapshots behind the published findings: each row is the SHA-256 (first 16 hex of the *decompressed* bytes) of a read-only evidence snapshot, frozen as-found. The frozen `.gz` archives live in the platform repository; anyone verifying a shared archive copy can match its decompressed SHA-256 against this table. Note the pre-change section: frozen **2026-08-25T14:43Z** — five days before the Sept 7 service change, and before any post-change data existed.

# Evidence freeze — pre-Sept-7 observed state

Frozen: 2026-08-25T14:43:02Z | Restored to canonical lineage (215d1d9): 2026-08-25T21:20Z
Purpose: pin the collector-side evidence behind quoted numbers BEFORE the
Sept-7 window. These are read-only evidence snapshots, never regeneration
inputs (PROTOCOL data-plane rule).

THIS IS THE SINGLE CANONICAL MANIFEST (DEC-11A). The duplicate
MANIFEST.md inside this directory carried a stale franken-lineage hash for
obs_lateness and was removed 2026-08-25T22:10Z — it caused a false
"drift/failure" verdict in T45's audit (alpha-3) before reconciliation.

Verification rule (DEC-12/S1): verify by decompressed-SHA against this
table. If obs_lateness.csv.gz is re-frozen post-window, a NEW manifest row
set is issued under a new heading — never silent in-place edits.

| Original file | Frozen archive (.gz) | SHA-256 (first 16) | Frozen bytes | Original bytes |
|---|---|---|---|---|
| obs_lateness.csv | obs_lateness.csv.gz | `b15fbec522a7cfc0` | 12,294,583 | 50,241,036 |
| occupancy_stats.csv | occupancy_stats.csv.gz | `21b2521c3e2ee71f` | 7,125 | 17,690 |
| ground_truth.csv | ground_truth.csv.gz | `38bd816be2f718fc` | 15,892 | 77,670 |
| ghost_trips.csv | ghost_trips.csv.gz | `ef0936157f56c217` | 8,336 | 26,317 |
| realized_waits.csv | realized_waits.csv.gz | `c98815b6dce212e3` | 2,662 | 7,199 |
| realized_waits.md | realized_waits.md.gz | `70da7301dc69737f` | 649 | 7,199 |

Note: obs_lateness is a live-growing artifact upstream; its freeze is a
POINT-IN-TIME snapshot. Growth after 14:43Z lives in live files, not here.

# Evidence freeze — post-Sept-7 observed state (v4 window)

Frozen: 2026-09-14T22:08:29Z (window Sept 7-13, 2026; findings v4 vintage)
Purpose: pin the collector-side evidence behind findings v4 and the Sept-22
scorecard. Read-only snapshots, never regeneration inputs (DEC-12/S1: verify
by decompressed-SHA against this table; NEW rows under a NEW heading only).

Window caveats (stamp rules, per the findings procedure):
- 2026-09-07 (changeover Sunday) and 2026-09-08 (VPS cutover; collector
  start 20:33) are PARTIAL days — never quotable as complete.
- 2026-09-09 .. 2026-09-13 COMPLETE. 2026-09-14 growth lives in live files.
- Known legacy artifact: 320,857 pre-2026-08-23 rows carry an empty date
  field (pre-date-column era, unique rows, not duplicates; zero empty-date
  rows in the collector's current output). Day-filtered analysis is
  unaffected; whole-file totals include them.

Vintage notes (per DEC-13: frozen as-found, with lineage):
- obs_lateness.csv, realized_waits.* — collector-side, synced from VPS
  2026-09-14 17:55 EDT after the perms-stall fix (see sync-stall receipt).
- occupancy_stats.csv, ground_truth.csv — backend/app/data vintages of
  2026-09-11 (post ledger-fix regen); ghost_trips.csv — 2026-08-25 vintage
  (data-share copy; pre-era population unchanged by the Sept-7 window).

| Original file | Frozen archive (.gz) | SHA-256 (first 16) | Frozen bytes | Original bytes |
|---|---|---|---|---|
| obs_lateness.csv | obs_lateness.csv.gz | `73e4d3745f5f5dfc` | 39,833,207 | 160,279,329 |
| occupancy_stats.csv | occupancy_stats.csv.gz | `ca44cfb8e9d143cf` | 11,564 | 32,708 |
| ground_truth.csv | ground_truth.csv.gz | `874a43c479710df3` | 24,254 | 106,164 |
| ghost_trips.csv | ghost_trips.csv.gz | `ef0936157f56c217` | 8,349 | 26,317 |
| realized_waits.csv | realized_waits.csv.gz | `c98815b6dce212e3` | 2,679 | 7,199 |
| realized_waits.md | realized_waits.md.gz | `70da7301dc69737f` | 667 | 1,234 |

Note: ghost_trips / realized_waits hashes are byte-identical to the pre-sept7
rows — expected, as those artifacts cover the pre-change era population and
were not regenerated in-window.

# Evidence freeze — v5 window (Sept 14–20 observed state)

Frozen: 2026-09-21T20:55Z (window Sept 14–20, 2026; findings v5 vintage)
Purpose: pin the collector-side evidence behind findings v5 and the Sept-22
scorecard. Read-only snapshots, never regeneration inputs (DEC-12/S1).

Window caveats (stamp rules, per the findings procedure):
- 2026-09-14 .. 2026-09-18 COMPLETE. 2026-09-19 **PARTIAL — collector gap
  01:28–12:54 EDT** (log: SESSION restarts 01:28:46 → no polls → 12:34:06 →
  12:54:50; first polls of the day 13:01). Morning service unobserved;
  1,204 scheduled trips correctly marked `uncovered` (never ghosts), obs
  volume 75,977 rows ≈ 37% of a weekday. 2026-09-20 COMPLETE (Sunday).
  Guardrail said 7/7 complete by Sept 22 — observed 6/7 + 1 partial ⇒ the
  v5 snapshot carries the caveat; freeze proceeds (day has data, not missing).
- obs_lateness frozen as-synced Sept 21 16:40 EDT (includes Sept 21
  in-window growth; day filtering excludes it). Same 320,857 legacy
  undated rows as v4 (excluded by day filtering).
- ghost_trips.csv regenerated 2026-09-21 16:52 (Sept 14–21 collections,
  --ledger upsert; Sept 19 gap reflected in uncovered counts).
- occupancy_stats / ground_truth — backend vintages as of 2026-09-21
  (occupancy_stats is a collection-wide aggregate, no date column —
  its figures are NOT window cuts; same caveat as v4).
- realized_waits.csv/.md — byte-identical hashes to both prior freezes
  (model artifact, not regenerated).

| Original file | Frozen archive (.gz) | SHA-256 (first 16) | Frozen bytes | Original bytes |
|---|---|---|---|---|
| obs_lateness.csv | obs_lateness.csv.gz | `320feef5b9346be7` | 49,158,845 | 196,853,165 |
| occupancy_stats.csv | occupancy_stats.csv.gz | `85870b7c35ebd124` | 12,680 | 34,158 |
| ground_truth.csv | ground_truth.csv.gz | `594b03face641791` | 26,525 | 115,558 |
| ghost_trips.csv | ghost_trips.csv.gz | `cc05923cd5fcf2ac` | 16,614 | 69,976 |
| realized_waits.csv | realized_waits.csv.gz | `c98815b6dce212e3` | 2,679 | 7,199 |
| realized_waits.md | realized_waits.md.gz | `70da7301dc69737f` | 667 | 1,234 |

> **ERRATA (2026-09-21, freeze day):** none. The Sept-19 gap was discovered
> BEFORE publication (this manifest) — stamps and caveats issued with the
> freeze, no post-hoc correction needed.

> **ERRATA (2026-09-14, same day, pre-publication):** the day-stamp caveats
> above were over-conservative. Empirical check (hourly distribution vs the
> Sept-9 control) shows 2026-09-08 is a COMPLETE day — the laptop collector
> carried it until the ~20:15 cutover, the scp seed merged its rows, and the
> VPS collector resumed 20:33 with the handoff gap invisible in counts
> (hour-20 delta 1%). 2026-09-07 (changeover Sunday) was fully laptop-side
> and is COMPLETE. All Sept 7-13 days: COMPLETE. The stamp rules for future
> windows stand; they simply had no occasion to fire this window.

# Evidence freeze — v6 window (Sept 21–27 observed state)

Frozen: 2026-09-28T20:45Z (window Sept 21–27, 2026; findings v6 vintage).
Read-only snapshots, never regeneration inputs (DEC-12/S1). Frozen as-found
per DEC-13, WITH the caveats below — analysis scripts must respect them.

| Original file | Frozen archive (.gz) | SHA-256 (first 16) | Frozen bytes | Original bytes |
|---|---|---|---|---|
| obs_lateness.csv | obs_lateness.csv.gz | `5b7a237c151deca2` | 53,986,926 | 223,600,376 |
| occupancy_stats.csv | occupancy_stats.csv.gz | `8b097744288ceeb7` | 12,871 | 34,512 |
| ground_truth.csv | ground_truth.csv.gz | `594b03face641791` | 26,292 | 115,558 |
| ghost_trips.csv | ghost_trips.csv.gz | `bdc97ca2ecd4d9e0` | 20,204 | 87,031 |
| realized_waits.csv | realized_waits.csv.gz | `c98815b6dce212e3` | 2,681 | 7,199 |
| realized_waits.md | realized_waits.md.gz | `70da7301dc69737f` | 667 | 1,234 |

Window caveats (stamp rules, per the findings procedure):

- **2026-09-21 .. 2026-09-23 COMPLETE** — 195,908 / 204,236 / 188,492 rows,
  zero duplicate observation keys.
- **2026-09-24 PARTIAL** — 151,422 rows; VPS died ~22:23 EDT (boot-end
  2026-09-25 02:23 UTC). Evening service unobserved from ~22:23.
- **2026-09-25 HEAVILY PARTIAL** — 12,149 rows (~6% of a weekday). Collection
  resumed 21:47 EDT after canary.timer fix; heartbeat RECOVERED 22:16.
  The ~23.5h outage (Sept 24 22:23 → Sept 25 21:47 EDT) is the
  T44-L2 coverage gap for this window; see
  `docs/runs/outage-postmortem-sept24-25.md`.
- **2026-09-26 COMPLETE** (Saturday) — 116,224 rows, no duplicate keys
  (consistent with the ~116k Saturday rate in the methods one-pager).
- **2026-09-27 COMPLETE cloud-side; frozen copy is MID-WINDOW (repeats expected).**
  CORRECTION (2026-09-28, post-freeze): the freeze-day "append storm /
  dedup failure" hypothesis is FALSIFIED by the coverage ledger
  (`coverage/collection_windows.csv`): all six Sept-27 windows ran on the
  cloud box (346/346, 342/342, 662/662, 444/445, 558/558 polls) and
  `append_rows` never had a per-key guard — multi-poll repeats within a
  window are the DESIGNED state, deduped only at window close
  (`collect_service.py` dedup_csv at startup + post-window). The frozen
  copy's mtime is 2026-09-27 22:44 — mid-evening-window — because the
  obs_lateness SYNC CHANNEL stalled at that point (small files kept
  syncing; the deadman's "collector heartbeat may be fine; the sync layer
  is not delivering" line describes exactly this). Raw-vs-unique figures:
  316,463 raw rows → 102,179 unique (date, route, stop, dep_time_min)
  keys; max 77×. **Analysis rule unchanged: any per-day analysis of Sept 27
  MUST dedup to the unique-key view** (identical to the pinned pipeline's
  freshest-horizon dedup, which the headline numbers already use); raw row
  counts are ~3.1× the unique-key count. When the sync channel recovers,
  the live file will jump to the cloud-side state (evening window deduped
  + Sept 28 growth); this freeze preserves the as-found 22:44 cut.
- ghost_trips.csv regenerated in-window (87,031 B vs v5's 69,976 B — more
  collections post-outage); ground_truth.csv byte-identical to v5
  (`594b03face641791`); realized_waits.* byte-identical to all prior freezes
  (model artifact, not regenerated).
- obs_lateness frozen as-found on the laptop 2026-09-28 — a MID-WINDOW
  copy (mtime Sept 27 22:44): the large-file sync channel stalled there
  while small files (coverage JSONs through Sept 28 15:00, canary) kept
  flowing. Sept 28 rows exist ONLY cloud-side; on recovery the live file
  jumps to the cloud state. A 220MB
  `obs_lateness.sync-conflict-20260925-221425-CSLQSVP.csv` from the
  outage-era sync conflict remains in the data home (owner action:
  archive); it is NOT part of this freeze.

Verification note: SHA-256s are of the UNCOMPRESSED bytes (first 16 hex,
truncated-`*` convention as v4/v5). Verify with e.g.
`python -c "import gzip,hashlib;print(hashlib.sha256(gzip.decompress(open('docs/runs/evidence-freeze-v6/obs_lateness.csv.gz','rb').read())).hexdigest()[:16])"`.

| UTC | label | file | size | sha256 (first 16) | archive |
|---|---|---|---|---|---|
| 2026-09-28T20:45Z | v6 | `obs_lateness.csv` | 223,600,376 B | sha256:5b7a237c151deca2* | `docs/runs/evidence-freeze-v6/obs_lateness.csv.gz` |
| 2026-09-28T20:45Z | v6 | `occupancy_stats.csv` | 34,512 B | sha256:8b097744288ceeb7* | `docs/runs/evidence-freeze-v6/occupancy_stats.csv.gz` |
| 2026-09-28T20:45Z | v6 | `ground_truth.csv` | 115,558 B | sha256:594b03face641791* | `docs/runs/evidence-freeze-v6/ground_truth.csv.gz` |
| 2026-09-28T20:45Z | v6 | `ghost_trips.csv` | 87,031 B | sha256:bdc97ca2ecd4d9e0* | `docs/runs/evidence-freeze-v6/ghost_trips.csv.gz` |
| 2026-09-28T20:45Z | v6 | `realized_waits.csv` | 7,199 B | sha256:c98815b6dce212e3* | `docs/runs/evidence-freeze-v6/realized_waits.csv.gz` |
| 2026-09-28T20:45Z | v6 | `realized_waits.md` | 1,234 B | sha256:70da7301dc69737f* | `docs/runs/evidence-freeze-v6/realized_waits.md.gz` |
