# TTC findings — window 1 (Mon 2026-10-12 → Sun 2026-10-18)

**Status: first TTC findings snapshot. Instrument-validation window, registered
before any lateness value was derived** (`docs/runs/two-city-study-design.md`
§5.2, registered 2026-10-12 mid-window with that fact disclosed; the window
closed 2026-10-18 and is quoted from 2026-10-27).

Every number below is produced by one command; nothing here is estimated:

```
cd backend && python scripts/derive_ttc_findings.py \
    --start 2026-10-12 --end 2026-10-18 --exclude-dates 2026-10-12 \
    --out ../docs/runs/ttc-w1-derivation-20261028.md \
    --json-out ../docs/runs/ttc-w1-derivation-20261028.json
```

Method constants are pinned in §5.2 and unchanged by this snapshot: near-term
rows only (|horizon| < 5 min), dedup = freshest horizon per
(route, stop, departure, date), early ≤ −2.0 min, n-floor 100 per cell, bands
H1 ≤5 / H2 5–10 / H3 10–20 min.

**Claim discipline (design §0):** instrument validation first, phenomena
second, causal silence always. Per-city blocks are never cross-ranked, and no
cross-city row appears in any table here.

## 0. Window integrity — read before quoting anything

### 0.1 Coverage

All seven service dates pass the pre-registered F4 gate (daily polls_ok ≥ 80%
of the window median). Median 688 → floor 550. Source:
`ttc-w1-derivation-20261027.json` → `health`, `f4_flags: []`; independently
re-derived by `backend/scripts/check_ttc_window.py --start 2026-10-12
--end 2026-10-18`, which exits 0. (Derivation commands now cite the
2026-10-28 pair; the original 2026-10-27 pair was withdrawn the same day —
its ghost construct had two defects, see §6.)

| date | day | polls_ok | unmatched | no_predictions | zombies | measurable entities |
|---|---|---:|---:|---:|---:|---:|
| 2026-10-12 | Mon (Thanksgiving) | 675 | 3.04% | 3.23% | 23,830 | 817,531 |
| 2026-10-13 | Tue | 690 | **7.07%** | 2.61% | 12,001 | 1,037,128 |
| 2026-10-14 | Wed | 687 | 2.73% | 2.66% | 1,629 | 1,103,143 |
| 2026-10-15 | Thu | 688 | 2.73% | 2.67% | 870 | 1,098,667 |
| 2026-10-16 | Fri | 679 | 2.74% | 2.68% | 129 | 1,089,624 |
| 2026-10-17 | Sat | 747 | 3.23% | 2.65% | 572 | 969,627 |
| 2026-10-18 | Sun | 1,844 | 2.45% | 2.79% | 14,463 | 2,451,985 |

**School context (mandatory):** Oct 12 is Thanksgiving, holiday service
(`backend/app/data/SCHOOL-CALENDAR.md:269`) — **excluded from every weekday
construct below** and retained only as holiday context. Oct 13–16 are normal
school-term weekdays; no PA day falls in this window (the next is Oct 26,
`SCHOOL-CALENDAR.md:270`). Oct 17–18 carry weekend service by definition.

### 0.2 Feed vintage (F2)

Pinned surface vintage `feed_version = S1000542`; the artifact
`gtfs_surface.zip` was written 2026-10-06 10:48, i.e. **before** the window
opened, and nothing in the directory is newer. **No mid-window rotation is
observable, so F2 does not fire and the window is not split.** Stated as the
limit it is: the TTC data dir carries no vintage-refresh log, so this is read
from the artifact's own mtime and `feed_info.txt`; an in-place overwrite that
preserved mtime would be invisible.

### 0.3 Sampling cadence asymmetry (still in force)

TTC weekday polls 675–747/day ≈ **116–128 s per poll**; MiWay over the same
dates polled **2,400–2,491/day** ≈ 35 s. MiWay therefore observed roughly
**3.6 polls per TTC poll** on weekdays. The weekend is much closer (Oct 18:
1,855 polls, 47 s) because a Sunday poll does less work — the same rate Oct 10
produced (1,821 polls). Per §5.2 this asymmetry is stated, never normalised,
and **no cross-city "rate of X per hour" figure is quotable** from this window.

Attribution, from the 2026-10-28 phase-timed probe
(`docs/runs/ttc-cadence-probe-20261028.md`, 8 profiled polls of the live feed):
per-poll WORK is bounded at ≤3.75 s (mean 2.65 s; TU fetch 0.35 s, decode
0.50 s, bind 1.67 s, VP phases 0.14 s) against the collector's 30 s target —
and a Sunday payload (~551 KiB TU, 1,580 entities) polls no faster than a
weekday payload locally. The weekday/weekend cadence gap is therefore the
collection box's documented memory-pressure slowdown (a 1 GB box whose polls
degraded 6.2–7.4 s → 30–76 s under swap per
`backend/scripts/vps/ttc-collector-memory.conf`), **not poll-loop structure**.
Measured consequence: parallel fetching and VP-stream decoupling were
considered and rejected — the cycle is ~11% occupied on capable hardware, and
a second interpreter's duplicate 37,675-trip index would worsen the box's
actual constraint.

### 0.4 Row accounting, and why "dedup removes nothing"

Raw near-term accounting: **6,183,323 rows → dedup 6,183,323 → near-term
5,786,976**; the 757,964 holiday rows are the Oct 12 block.

The dedup step removing zero rows is **correct, not broken**: the collector
already collapses at write time. Verified on 2026-10-15 — 921,445 rows,
921,445 distinct `(route_short_name, stop_id, dep_time_min, date)` keys, zero
repeat keys. The derivation's dedup is a no-op on this data by construction.

### 0.5 Band construction — three defects fixed before this snapshot was written

The first real run (2026-10-27, same window) produced a band table that could
not be published. All three are fixed in
`backend/scripts/derive_ttc_findings.py`; the numbers in §2 are from after the
fixes.

1. **Terminus elected by ordinal, not stop.** `terminus_headways` ranked the
   last stop by `stop_sequence`, which is an ordinal: on a branched or
   short-turning route several *different* terminuses share it. Route 52
   direction 0 has 261 trips whose pattern is two stops long, so ordinal 2 was
   the modal "terminus" and the code measured gaps between unrelated trips.
   Now elected by `stop_id`, and departures are taken only from trips that
   actually end there. Regression test:
   `test_terminus_ranks_by_stop_id_not_ordinal`.
2. **Rows banded by route, not route-direction.** §5.2 registers the band on
   *each surface route-direction*, but observations carry no direction — so
   the first implementation collapsed each route to its modal direction and
   broke 1–1 ties by `value_counts` order. **23 of 220 routes have directions
   straddling a band edge** (route 29: 16.0 min one way, 8.0 the other; route
   52: 18.0 and 10.0). Rows are now banded by their bound trip's own
   direction (`trip_bands`). Tests: `test_trip_bands_use_each_trips_own_direction`,
   plus an int-route-id fixture because the real feed's int route ids made the
   str-keyed join return an empty map silently — the first run of the fix
   looked like it worked and had changed nothing.
3. **The F1 falsifier was a tautology.** It kept rows whose
   `(trip_id, stop_sequence)` existed in the static pattern — but the collector
   *binds to* static trips, so every row passed and F1 printed identical shares
   to three decimals in every band. It now also requires the row's `stop_id` to
   be the stop that pattern places at that sequence, which is what a wrong-slice
   bind fails (`test_f1_pattern_verified_requires_the_patterns_own_stop`). A
   cell that cannot be evaluated now prints **NOT TESTABLE**, never "persists".

**Disclosure carried into every band figure:** 727,831 near-term rows
(**14.47%**) have no static trip to band by and took their route's modal band —
these are the rotating trip ids §5.1 warns about, counted rather than silently
absorbed.

**What a band number is, precisely:** the median consecutive scheduled
departure gap **at the busiest branch terminus** of a route-direction, over the
window's weekdays. It is therefore a *branch* headway. On a branched route the
trunk headway (where branches merge) is higher-frequency and is **not** what
the table reports.

## 1. Instrument health — the primary claim's evidence

The §0-safe claim is that the instrument runs unmodified on a second agency.
On this window: **6 of 7 days hold unmatched at ≤3.23%**, no_predictions is
stable at 2.45–3.23%, and the poll layer succeeded
**6,010 / 6,021** attempts (99.8%). Zombie drops total 53,494 and are
concentrated on two dates (Oct 12: 23,830; Oct 18: 14,463).

**F3 fires on Oct 13** at 7.07% unmatched (> 5%). This was recorded mid-window
as §5.2's "F3 has already flagged a day" note (7.07% there), so it is not a
close-time discovery. Per F3 it does not block the week; it is carried here as
a flag with the day named.

Read as a window average the same figure is 3.4% and flags nothing — which is
exactly why the day-level counters matter (`app.ttc_counters`): a whole-window
ratio cannot catch one bad day.

**Verdict: supported for the instrument-health construct.** The binding layer
degrades on one day of seven and recovers without intervention; the pipeline
runs on TTC's real-time feed unmodified.

## 2. Earliness by band (weekdays only, Oct 13–16; n = 5,029,012)

> **Standing caveat (design §5.1, registered 2026-09-29 pre-collection).** TTC
> earliness share is an UPPER BOUND on true earliness — time-at-anchor binding
> under sub-headway lates can attach a late trip to the NEXT scheduled trip.
> **TTC earliness and MiWay earliness are NOT the same construct.**

| Band | early share (≤ −2 min) | late ≥ 5 min | median lateness | n |
|---|---|---|---|---|
| H1 (≤5 min) | 20.1% | 4.7% | −0.17 min | 20,818 |
| H2 (5–10 min) | 26.7% | 5.0% | −0.37 min | 2,768,952 |
| H3 (10–20 min) | 25.9% | 7.0% | −0.25 min | 1,666,551 |

- **F1 (pattern restriction):** the three bands' early shares are unchanged at
  0.0% drop, with **0 rows excluded as stop-mismatched** out of 4.46M verified
  rows. The falsifier is now capable of firing and does not: on this window the
  binds land on the pattern's own stop everywhere. That is a statement about
  *misbinding to the wrong stop*, not about §5.1's sub-headway ambiguity, which
  the upper-bound caveat covers and F1 cannot test.
- **F5 (schedule anchoring):** no H1 route met the anchored criterion
  (MAD < 0.25 min); nothing was excluded from the H1 cell.
- **Band population, and a contradiction with the design's expectation:** H1
  contains **one route — 320 — in two directions**. The design's illustrative
  H1 core (52 / 36 / 29) measures 18.0/10.0, 6.0/6.0 and 16.0/8.0 min
  respectively, i.e. H2–H3. That is a consequence of the registered definition
  (a **whole-service-day median** at a branch terminus), in which off-peak
  service dominates: a peak-only 3-min route still has a ~6–10 min daily
  median. The band edges are not wrong; the definition measures a different
  thing from "high frequency". Changing it to a peak-period headway would be a
  §5.2 amendment, not a bug fix, so **this snapshot does not change it**.
- 141 of 440 route-directions fall outside all three bands (>20 min branch
  headway or no computable terminus) and are reported only in the
  whole-network instrument blocks, per §5.2.

## 3. Worst routes (TTC-local; n-floor applies, never cross-ranked)

| route | median lateness | n |
|---|---:|---:|
| 160 | +1.53 min | 9,231 |
| 49 | +1.37 min | 7,177 |
| 938 | +1.28 min | 750 |
| 162 | +0.95 min | 10,900 |
| 985 | +0.95 min | 3,492 |

These are within-city context only. They are not compared to MiWay routes and
no comparable MiWay construct exists on the same basis.

## 6. Ghost/silent-trip rate (added 2026-10-28; per-city, not comparable)

The TTC ghost construct now exists (§3.4 of the design, NEW-trip-aware) and
gives, from the 2026-10-28 derivation: weekday aggregate **2.75% (1 in 36)**
silent (Mon–Fri, Oct 13 excluded as DEGENERATE — see notes), Sunday Oct 18
**8.09%** (2,347 of 29,023 verifiable) with **39%** of its attributed rows
occurring Monday Oct 19 (after-midnight carry), Saturday Oct 17 7.06% with 41%
carry.

Route-level split of the Sunday silence (2026-10-28, from the derivation's
per-day `silent_routes`): the distribution is FLAT — the worst route (900)
carries only 157 of 2,347 silent trips (6.7%), route 47 has 81 (3.5%), and the
top ten routes together account for ~25%. No route pathology: the weekend
rate is network-wide, which is consistent with a feed-side (instrument or
service-information) cause rather than a specific route failure.

Cause coverage, honestly: this construct cannot separate a trip that did not
run from one the feed never reported while it was watched. The day counters
count the matching phenomena but only at entity granularity, never persisted:
on Sunday, 48,350 SKIPPED stop announcements (31% of the window's 156,666 skipped stop announcements) and 14,463 zombie entities were dropped, and 0 NEW trips were inserted.
The instrument improvement that would decompose the Sunday 8.09% into
"cancelled vs feed-skipped vs vanished" is for the collector to persist
skipped `(trip_id, stop)` events alongside the counters — noted as design
§1 backlog, not built this window.

> **Weekend-rate caveat (2026-10-28 diagnosis).** Two construct defects
> manufactured large weekend rates before being fixed that day: keying on
> raw occurrence dates (then fixed by service-date attribution), and cutting
> the construct's input by occurrence date before attribution (fixed by
> extending the input through end+1 with a matching attribution scan —
> regression-tested: `test_ghost_window_input_includes_the_next_days
> _occurrence_rows`, `test_ghost_attribution_scans_through_the_inputs
> _max_occurrence`). Rates for any window's last day from runs earlier than
> 2026-10-28 are inflated by the second defect and must not be quoted.
> Both caveats live in `ttc-w1-derivation-20261028.md` (rule paragraphs and
> the per-day notes), which the command above regenerates.

## 4. What this window does NOT say

- **No NEW units for the ghost rate beyond §6.** The construct exists (added
  2026-10-28, two same-day defect fixes regression-tested); §6 carries the
  numbers and their caveats rather than estimating a residual.
- **No headway regularity / bunching indicator.** Design §1 row 3 is
  unbuilt. Nothing in §2 is a regularity measure.
- **No skipped-stop metric.** TTC-only capability, not derived.
- **No cross-city comparison of any kind**, including earliness, and no causal
  statement (design §0). The sampling asymmetry of §0.3 alone blocks any
  "per hour" comparison.
- **Not a whole-network earliness figure.** The 14.47% unbanded-by-trip rows
  (§0.5) and the 141 out-of-band directions mean §2 covers the banded
  population, not "TTC".

## 5. Bottom line

The instrument runs unmodified on a second agency's real-time feed and produces
internally consistent results on six of seven days, with one flagged day named
(Oct 13). That is the claim this study was built to make, and it holds.

The earliness shares (20–27% early ≥2 min, median lateness −0.17 to −0.37 min)
**exist** on this network and are reported per band with the §5.1 upper bound
attached; they are not comparable to MiWay's construct and are not a ranking.

What the window changed about the instrument is more useful than what it said
about the network: three band-construction defects and a tautological falsifier
were found by running it on real data before publishing, which is the sequence
the design exists to enforce.
