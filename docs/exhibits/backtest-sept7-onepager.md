# Backtest: the optimizer's pre-registered recommendations vs. MiWay's actual Sept 7 change

**Question.** Before Sept 7, the optimizer recommended per-route departure shifts (±5 min, zero new service) and a pre-registered prediction file committed those bands publicly on 2026-08-24. MiWay then shipped its own Sept 7 change. Where the two agree, the tool predicted an agency decision; where they differ, the gap is the finding.

**Rules were locked before scoring** (`docs/runs/backtest-sept7-plan.md`): a recommendation MATCHES if MiWay moved the same route in the same direction within ±3 min (am-rush band, mean first-departure, ≥3 trips/band). Pre/post schedules come from the two service-id families (26AU03 → 26SE07) inside the byte-identical feed zip. **Headways are per-direction median gaps** (correction of 2026-09-24: naive window÷trips formulas double-count directions and ignore band widths; corrected values match the route reference, e.g. 109 midday ≈15 min).

---

## Verdict strip

| Score | Result |
|---|---|
| Recommendations scored | 42 routes (pinned pre-reg basis, 20260805) |
| **MATCH (same sign, ±3 min)** | **5 / 42 (11.9%)** |
| NEAR-MISS (same sign, off-magnitude) | 2 / 42 → **16.7% same-direction** |
| DIFFERENT | 35 |
| Announced routes (8/66/43/109) | **1 of 3 scored matched — route 8: recommended +5.0, actual +6.91** |
| Pre-registered scorecard, as emailed (7 metrics) | 0 passed / 4 failed / 2 unscoreable / 1 failed-low |
| Layers A+C mechanical re-derivation (20 pre-reg rows) | **3 PASS · 8 FAIL (4 low / 3 high / 1 catch-all) · 1 guardrail VIOLATED · 8 UNSCOREABLE** |
| Guardrails (pre-reg §4) | 45→109 held (−3.34 min vs ≤ +1.0); unscoped no-pair->2min **broke** (13→46 +2.70, 44→46 +2.42); 8/66-pairs unscoreable at this stop |

The five matches: 18 (−3.0 rec / −1.36 actual), 36 (+2.0 / +1.20), 44 (+3.0 / +4.52), 49 (−3.0 / −2.25), **8 (+5.0 / +6.91, announced)**. Near-misses: 2 (+4.0 / +0.90), 51 (−5.0 / −0.53). Verdict set is stable across the headway-method correction (same 5/2/35 route split as the first run).

## Three layers, one contract

| Layer | Question | Result | What I got wrong |
|---|---|---|---|
| **A — scorecard** | Do the banded predictions hold against frozen artifacts? | 2 PASS / 6 FAIL / 1 UNSCOREABLE (9 rows) — reproduces the emailed 0/4/2/1 story | good-direction misses score as failures (kept, not smoothed); Route 2 "eased" not reproducible — below |
| **B — recommendations** | Do the 42 recommended shifts match what MiWay shipped? | 5/42 match, 16.7% same-direction; lift degenerate (MiWay moved every route) | first pass used wrong headway math (caught, corrected) |
| **C — pair bands** | Did Meadowvale terminal waits move as banded? | 45→109 better than band; flat catch-all broken 75/88; unscoped guardrail **VIOLATED** | 5 named pairs unscoreable (harness vintage NaN); guardrail stated scoped in the email, unscoped in the pre-reg |

Full row-by-row verdicts: `docs/runs/backtest-sept7-layers-AC.md` (bands quoted verbatim from the frozen pre-registration; rerunnable via `backend/scripts/backtest_layers_ac.py`).

## What MiWay actually did (the structural finding)

**Sept 7 was a capacity change, not a re-phase.** 84 route/band cells moved by >0.5 min; **70 of them changed trip counts** — headway surgery, not clock-shifting. Biggest gains (per-direction headway): 110 midday 21.0→12.0 min (34→61 trips), 26 late-night 27.0→14.5, 126 midday 20.0→14.0, 110 PM 22.5→12.0, 8 am-rush 34.2→25.8. The optimizer's recommendations — pure re-phasing at zero cost — were structurally a different *kind* of intervention than what the agency bought. The 14 stable-count bands are where an offset comparison is clean.

The announced centerpiece did not get frequency: **route 109's midday headway is unchanged (15.0 → 15.0 min per direction)** — its midday pattern re-timed ~10 min later, where the tool recommended +5 (a 4.9-min mismatch). Route 66 moved *earlier* (−4.34 min mean first-departure) where the tool recommended later (+5). Announcement and timetable were not the same document.

## What I got wrong (logged, not smoothed)

1. **First run quoted wrong headways** (window÷trips, directions pooled) — caught by the owner, who flagged it as a recurring agent failure mode; corrected to per-direction median gaps and every number in this exhibit re-derived. The route-reference cross-check (109 midday ≈15 min) is now a standard step in `.agents/CORRECTIONS.md`.
2. **The plan's chance-rate/lift statistic degenerated**: MiWay changed *every* route in the scoring universe (57/57), so chance = 1.0 and lift is undefined. Raw agreement rates are reported instead.
3. **Composition caveat on three matches**: routes 44 and 8 also changed trip counts in the scored band, so their mean first-departure shift is partly pattern composition, not a pure re-phase (18/36/49 are the clean ones).
4. **Scoring-band convention**: offsets are uniform per route, so they were scored against the am_rush band (first departures of the service day) — a choice, locked in the rules file before running.
5. **The catch-all band broke in both directions**: 75 of 88 non-named pairs moved more than ±0.5 min — Sept 7 restructured the terminal far beyond what the pre-registration imagined (Layer C).
6. **A guardrail stated unscoped was violated.** The pre-reg said no Meadowvale pair degrades >2 min; 13→46 (+2.70) and 44→46 (+2.42) crossed it. The follow-up email's scoped reading ("pairs I'd predicted would move") holds — but the pre-reg's wording does not.
7. **One sent number stays unreconciled.** The email's Route 2 midnight "42% → 37%" came from a trip-level readout with no artifact located; on the pre-reg's own period-mean basis the frozen CSVs say 42.5 → 44.8 — worse. Artifact wins until the original readout surfaces (reconciliation owed, logged in STATUS).

## Reading

An independent, zero-cost optimizer and a real agency planning process agreed on direction-and-magnitude about one time in six, including an announced route re-timed within 1.9 minutes of the recommendation. The honest conclusion is not "the tool predicts MiWay" — it is that **re-timing and capacity are substitute levers**, and the agency's revealed preference under a real budget is capacity. The 66 sign-flip (announced route) is the concrete case where the two optimization philosophies diverge; the 109's flat midday frequency shows the announcement's headline and the timetable's delivery were different things.

---

*Artifacts: optimizer offsets `docs/runs/backtest-sept7-optimizer-offsets.json` (pinned solve, params logged); actual-change table `docs/runs/backtest-sept7-actual-change.json` (v2, per-direction headways); match table `docs/runs/backtest-sept7-matches.json`; Layers A+C verdict table `docs/runs/backtest-sept7-layers-AC.{json,md}` (mechanical re-derivation, 20 rows, bands verbatim); rules + integrity pre-registration `docs/runs/backtest-sept7-plan.md`; prediction bands `docs/runs/pre-registration-sept7.md` (committed 2026-08-24). Feed vintage: 26AU03 (2026-09-02) vs 26SE07 (2026-09-08) via `gtfs_kit.service_ids_on`. Headway cross-check: `backend/app/data/route_reference.md` (109 midday "every ~15 min").*
