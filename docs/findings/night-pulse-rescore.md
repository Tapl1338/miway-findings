# Night pulse re-score: what the September retime fixed, measured after midnight

> **Provenance:** measured from the transit system's own public
> real-time feed as collected by the project's 24/7 poller — 65 poll
> files, Sept 8–18 2026 (11 post-schedule-change service days).
> Methodology identical to the pre-change audit (same detector, same
> geofences, same guards); this page is verified token-for-token against
> its private twin on every push. Miss rates are conservative lower
> bounds on the true rate (the detector's stated bias), and the
> geofence robustness noise floor is ~7 percentage points.

## The question

When a bus route ends its run at a terminal and another route's bus
departs from the same bay a few minutes later, the schedule is promising
a pulse: the incoming rider walks off one bus and straight onto the
other. After midnight, with long gaps between departures, a missed pulse
is not a 10-minute annoyance — it can be a 30-minute wait at 1 a.m.

The pre-change audit (published in the v3 snapshot era) found terminal
pulse misses at 8–33% across six audited pairs, worst 2→66 at City
Centre (~30–35%), driven by outbound partners holding 3–7 minutes past
the pulse minute. The September 7 retime publicly claimed to fix 2→66
"to 0 minutes". This re-score measures, on 11 days of post-change
nights, what actually happened — including whether the fix held.

## How a pulse is measured

For each pulse pair — route A terminating at a terminal, route B
originating there, scheduled within 8 minutes — the detector
reconstructs, per service date: A's observed arrival (last stopped-at
sighting within 500 m of the terminal) and B's observed departure (first
in-transit sighting within 1,200 m, past the layover). A pulse **misses**
when B's bus physically departs before A's rider arrives. Two pollution
guards apply: only in-transit sightings count as departures (no layover
pollution), and trip IDs must share the same service date (no stale-date
pollution). Both windows are reported: the night window (23:00–05:30
scheduled, the pre-registered basis) and a daytime control (07:00–19:00)
that answers a different question — whether the pulse geometry survives
at full headways.

## Night window (the pre-registered basis) — Sept 8–18

| Pair (terminal) | Events | Missed % | Median gap | p10 | p90 |
|---|---|---|---|---|---|
| 3→61 @ City Centre | 16 | **50%** | **−0.5 min** | −6.2 | +8.7 |
| 2→66 @ City Centre | 19 | **0%** | +7.9 min | +1.1 | +13.5 |
| 2→17 @ City Centre | 15 | 13% | +5.1 min | −0.4 | +7.4 |
| 42→46 @ Meadowvale | 16 | **0%** | +6.0 min | +4.4 | +10.4 |
| 46→42 @ Meadowvale | 15 | 33% | +0.6 min | −4.0 | +3.9 |
| 38→44 @ Meadowvale | 0 | — | — | — | — |

38→44 has no same-night co-occurrences at all in 11 days: the pair is
not scheduled within 8 minutes of each other after midnight, so its
night "pulse" does not exist (the daytime control shows it missing 30%
of the time anyway). Its first cut (7 days) showed the same.

## The daytime control (07:00–19:00) — Sept 8–18

| Pair (terminal) | Events | Missed % | Median gap | p10 | p90 |
|---|---|---|---|---|---|
| 3→61 @ City Centre | 402 | 29% | +3.6 | −6.9 | +11.6 |
| 2→66 @ City Centre | 477 | 32% | +3.9 | −7.3 | +11.5 |
| 2→17 @ City Centre | 433 | 38% | +1.7 | −9.9 | +11.7 |
| 42→46 @ Meadowvale | 182 | 9% | +6.8 | +0.0 | +14.7 |
| 46→42 @ Meadowvale | 188 | 15% | +6.2 | −2.3 | +11.2 |
| 38→44 @ Meadowvale | 175 | 30% | +3.9 | −2.9 | +11.0 |

The control is kept and labeled because it answers a different question
than the night window — not quoted interchangeably with it.

## What the doubled sample changed

The first post-change cut (7 days, 8–12 events per pair) produced four
conclusions; this refresh (11 days, 15–19 events per night pair) is
their replication test:

1. **The 2→66 fix is real and confirmed.** 0% missed at n=19 (first cut
   n=12), median cushion +7.9 min — the outbound partner holds well
   past the pulse minute, exactly what the retime designed. The
   daytime control still misses 32%, so the geometry remains fragile
   off-pulse; the scheduled night pulse itself is fixed.
2. **42→46's improvement is confirmed.** 0% missed at n=16 (first cut
   n=8, flagged small), median +6.0. The pre-change "median miss not
   fixed" status is retired for the night window.
3. **38→44 remains de-facto unpulsed at night** — zero co-occurrences
   confirmed through 11 days.
4. **3→61, a pair the retime did not announce, is the worst night pair —
   and worse than first measured.** 50% missed (first cut 42%) and the
   median gap crossed negative: −0.5 min. The inbound bus now typically
   arrives *after* its outbound partner has already left. Route 3 is
   the flagship high-frequency corridor; this pair degraded by 2
   minutes in the same retime.
5. **Each terminal has exactly one broken night direction.** City
   Centre's is 3→61; Meadowvale's is 46→42 (33% missed, median +0.6, at
   doubled n). The pattern was invisible at the first cut's sample size.

**Verdict for the pre-registered comparison: mixed-to-improved, with
confidence upgraded.** The worst pre-change pair is fixed and confirmed;
one Meadowvale improvement is confirmed; one pair is confirmed unpulsed;
the new worst pair is confirmed and worsening.

## First cut vs refresh, pair by pair

The replication test in numbers — every first-cut conclusion re-measured
on nearly double the sample (night events per pair: 8–12 → 15–19; daytime
104–282 → 175–477):

| Pair | First cut (Sept 8–14) | Refresh (Sept 8–18) |
|---|---|---|
| 3→61 @CC | 42% missed, median +0.8 (n=12) | **50% missed, median −0.5** (n=16) |
| 2→66 @CC | 0% missed, median +7.6 (n=12) | **0% missed, median +7.9** (n=19) |
| 2→17 @CC | 20% missed, median +4.1 (n=10) | 13% missed, median +5.1 (n=15) |
| 42→46 @MDVL | 0% missed, median +5.7 (n=8) | **0% missed, median +6.0** (n=16) |
| 46→42 @MDVL | 25% missed, median +0.8 (n=8) | **33% missed, median +0.6** (n=15) |
| 38→44 @MDVL | no night events (7 days) | no night events (11 days) |

Daytime control, first cut → refresh: 3→61 28%→29%, 2→66 34%→32%, 2→17
39%→38%, 42→46 7%→9%, 46→42 14%→15%, 38→44 26%→30% — every pair stable
within a few points. The night window is where the conclusions moved,
because that is where the sample doubled.

## Where this feeds

The per-pair table above is the Section-2 baseline of the project's
late-October pre-registration (both terminals this time), and the 2→66
fix line — now at doubled sample — pairs with the 3→61 line as the
honest both-halves story for the civic follow-up: the retime fixed a
real, measured defect, and this measurement names what still misses.

*Measured 2026-09-18 from 65 poll files, Sept 8–18 2026. First cut
(7 days) published 2026-09-15; this refresh supersedes it with doubled
night samples. Raw per-pair tables preserved in the private repo.*

**Provenance detail.** Corpus bounds 2026-09-08 → 2026-09-18 (detector
window stamp 20260908..20260918); geofence robustness noise floor from
the 2026-09-06 audit (~7 pp); first-cut receipt dated 2026-09-15
(night-pulse-rescore-20260915.md); the project's late-October
pre-registration template had its pulse baselines first filled
2026-09-14 from the 7-day cut, refreshed from this receipt.
