# Sept-7 pre-registration scorecard — FINAL receipt

> **Provenance:** published verbatim from the project's private measurement
> repo — the frozen scorecard receipt generated 2026-09-22 by the mechanical
> scorer (`sept7_scorecard.py` lineage). Nothing is summarized or trimmed:
> the misses and UNMEASURABLE verdicts appear exactly as scored. This page
> is verified token-for-token against its private twin on every push.

**Mode:** FINAL — post-change weekday service days collected: **11** / required 10 (2026-09-08 … 2026-09-22)
**Generated:** 2026-09-22T17:53:40

## Section 3 — feed-side metrics (computed directly)

| Metric | Frozen baseline | Pre-registered band | Post-change | Verdict | n |
|---|---|---|---|---|---|
| Early departures (>=2 min early, FQ-10) | 30.7% | 29.0–33.0% | 23.0% | FAIL | 2,014,368 |
| AM peak (07–09) early rate | 37.0% | 35.0–39.0% | 28.3% | FAIL | 243,711 |

*Basis note: the frozen baseline was counted pre-FQ-10; the post-change column is FQ-10 canonical (measured rows, horizon <= 0, lateness <= -2.0). Same basis as findings v4 — do not mix bases across snapshots. For a like-for-like read: the FQ-10 pre-change week (v3) measured 26.3%, which is ALSO outside the 29–33 band — so a below-band FAIL is not a basis artifact; it is the pre-registration's stability prediction being wrong in the improvement direction.*

| Route 109 PM-rush mean occupancy | 40% | 38.0–42.0% | 45.8% | FAIL | 46,741 |
| Route 2 midnight mean occupancy | 42% | 40.0–44.0% | 36.7% | FAIL | 25,071 |

*Crowding basis: window-scoped (raw corpus, scoring dates). Raw APC signal, uncorrected. Window-scoped means re-aggregate the raw snapshots within the scoring dates (same era discipline as the other rows); the collection-wide fallback mixes eras and is advisory only — windowed_crowding.py is the standing tool.*

| Ghost trip rate | 2.87% | 2.5–3.5% | 0.40% (new-vintage ledger) | UNMEASURABLE | 59,123 |

*Ghost basis note: UNMEASURABLE by design. The pre-registered baseline (2.87%) was measured on a detector vintage the ledger has since replaced — the vintage audit (docs/runs/ghost-ledger-vintage-audit.md) re-based the pre-change rate to 1-in-63, so no like-for-like denominator exists and the band cannot be scored mechanically. The era-split figure shown (post-change service dates only, verifiable denominator, raw-ledger never quoted) is informational; the auditable artifact is the window receipt (docs/runs/ghost-v4-window-20260914.md). Trips scheduled during collector downtime are uncovered, never ghosts.*

## Section 1 — GTFS re-run (invoke the frozen harness)

Pre-change zip: `miway_gtfs_2026-08-23_pre-sept7.zip` SHA-16 `f43fb0a9de891dbd` — matches pre-registration.
Run per protocol: `sept7_compare.py --old-zip <pre> --new-zip <post>` and `equity_report.py` with identical args; paste JSON outputs beside this file and the bands (9,500–10,000 pax-min; Ward 9 +1.5–+3.5; 13–17 worse-off) score mechanically.

## Falsification criteria check

- #5 early-rate outside 27–35%: TRIGGERED
- #1/#2 (model metrics) and #3/#4/#6: pending the Section 1 runs above.

## Section 1 — GTFS re-run (FINAL, executed 2026-09-22)

Pre-change zip SHA-16 `f43fb0a9de891dbd` verified against pre-registration.
Runs: `sept7_compare.py --old-service-date 20260905 --new-service-date 20260914`
(output: `sept7-compare-final-20260922.json`) and `equity_report.py` paired
runs with pre-registered solver params (all_day / ridership / 6,000 connections
/ ±5 min / 120 s) and the stop→ward lookup (`ward_stops.csv`):

| Band | Pre-registered | Old side (26AU03) | New side (26SE07) | Verdict |
|---|---|---|---|---|
| Network saved_pax_minutes | 9,500–10,000 | 10,179.6 (OPTIMAL) | 19,368.0 (OPTIMAL) | UNMEASURABLE-AS-REGISTERED |
| Ward 9 optimization delta | +1.5 to +3.5 improvement | −0.13 (14 stops, 8 worse-off) | −0.01 (5 stops, 3 worse-off) | FAIL-LOW |

*Basis note (memo Decision 3, pre-made): the pre-registration's 9,737.7
pax-min baseline was produced on the then-current ridership weighting; this
re-run uses the same pre-registered solver params but the current ridership
dataset with measured floors. The like-for-like read is the OLD-vs-NEW pair
computed identically: 10,179.6 (26AU03) → 19,368.0 (26SE07), solver OPTIMAL
on both. The pre-registered band is scored UNMEASURABLE-AS-REGISTERED (basis
superseded); the paired re-run is the auditable exhibit.*

*Ward 9 note: the changeover timetable effectively erased the ward's
optimization headroom (−0.13 → −0.01, and its stop set in the optimized
solution shrank 14 → 5). Both readings sit far below the pre-registered
+1.5–+3.5 improvement band → FAIL-LOW, matching the memo's dry-run
expectation. Fragility note: the daily spread on route-2 midnight is ±15
points, so the 40–44 band FAIL should be quoted with the pre-drafted
fragility line.*

## FINAL tally (7 registered bands)

1. Early departures (network) — **FAIL** (below band, improvement direction)
2. AM peak early rate — **FAIL** (below band, improvement direction)
3. Route 109 PM occupancy — **FAIL** (above band)
4. Route 2 midnight occupancy — **FAIL** (below band; ±15pt daily spread fragility note applies)
5. Ghost trip rate — **UNMEASURABLE** (detector vintage replaced; by design)
6. Network saved_pax_minutes — **UNMEASURABLE-AS-REGISTERED** (basis superseded; paired exhibit: 10,179.6 → 19,368.0)
7. Ward 9 delta — **FAIL-LOW** (optimization headroom erased by changeover)

Score: **0 PASS / 4 FAIL / 1 UNMEASURABLE / 1 UNMEASURABLE-AS-REGISTERED / 1 FAIL-LOW.**
Every miss is published with its cause — the pre-registration did its job:
it predicted stability and the changeover delivered change.
