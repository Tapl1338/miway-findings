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

The five matches: 18 (−3.0 rec / −1.36 actual), 36 (+2.0 / +1.20), 44 (+3.0 / +4.52), 49 (−3.0 / −2.25), **8 (+5.0 / +6.91, announced)**. Near-misses: 2 (+4.0 / +0.90), 51 (−5.0 / −0.53). Verdict set is stable across the headway-method correction (same 5/2/35 route split as the first run).

## What MiWay actually did (the structural finding)

**Sept 7 was a capacity change, not a re-phase.** 84 route/band cells moved by >0.5 min; **70 of them changed trip counts** — headway surgery, not clock-shifting. Biggest gains (per-direction headway): 110 midday 21.0→12.0 min (34→61 trips), 26 late-night 27.0→14.5, 126 midday 20.0→14.0, 110 PM 22.5→12.0, 8 am-rush 34.2→25.8. The optimizer's recommendations — pure re-phasing at zero cost — were structurally a different *kind* of intervention than what the agency bought. The 14 stable-count bands are where an offset comparison is clean.

The announced centerpiece did not get frequency: **route 109's midday headway is unchanged (15.0 → 15.0 min per direction)** — its midday pattern re-timed ~10 min later, where the tool recommended +5 (a 4.9-min mismatch). Route 66 moved *earlier* (−4.34 min mean first-departure) where the tool recommended later (+5). Announcement and timetable were not the same document.

## What I got wrong (logged, not smoothed)

1. **First run quoted wrong headways** (window÷trips, directions pooled) — caught by the owner, who flagged it as a recurring agent failure mode; corrected to per-direction median gaps and every number in this exhibit re-derived. The route-reference cross-check (109 midday ≈15 min) is now a standard step in `.agents/CORRECTIONS.md`.
2. **The plan's chance-rate/lift statistic degenerated**: MiWay changed *every* route in the scoring universe (57/57), so chance = 1.0 and lift is undefined. Raw agreement rates are reported instead.
3. **Composition caveat on three matches**: routes 44 and 8 also changed trip counts in the scored band, so their mean first-departure shift is partly pattern composition, not a pure re-phase (18/36/49 are the clean ones).
4. **Scoring-band convention**: offsets are uniform per route, so they were scored against the am_rush band (first departures of the service day) — a choice, locked in the rules file before running.

## Reading

An independent, zero-cost optimizer and a real agency planning process agreed on direction-and-magnitude about one time in six, including an announced route re-timed within 1.9 minutes of the recommendation. The honest conclusion is not "the tool predicts MiWay" — it is that **re-timing and capacity are substitute levers**, and the agency's revealed preference under a real budget is capacity. The 66 sign-flip (announced route) is the concrete case where the two optimization philosophies diverge; the 109's flat midday frequency shows the announcement's headline and the timetable's delivery were different things.

---

*Artifacts: optimizer offsets `docs/runs/backtest-sept7-optimizer-offsets.json` (pinned solve, params logged); actual-change table `docs/runs/backtest-sept7-actual-change.json` (v2, per-direction headways); match table `docs/runs/backtest-sept7-matches.json`; rules + integrity pre-registration `docs/runs/backtest-sept7-plan.md`; prediction bands `docs/runs/pre-registration-sept7.md` (committed 2026-08-24). Feed vintage: 26AU03 (2026-09-02) vs 26SE07 (2026-09-08) via `gtfs_kit.service_ids_on`. Headway cross-check: `backend/app/data/route_reference.md` (109 midday "every ~15 min").*
