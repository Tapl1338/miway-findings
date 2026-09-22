# Pre-Registration: Week of Sept 28 – Oct 4, 2026 (stability test III)

**Committed:** 2026-09-22 (before any Sept 28–Oct 4 analysis; 0 of 7 window days complete)
**Status:** PRE-REGISTRATION — NEEDS-VERIFY by non-author handle
**Purpose:** Falsifiable week-over-week predictions for the Sept 28 – Oct 4 collection window. Fourth in the series ([sept7](pre-registration-sept7.md), [sept14-20](pre-registration-sept14-20.md), [sept21-27](pre-registration-sept21-27.md)). This registration is the first written **after a FINAL scorecard verdict existed** — the Sept-7 FINAL scored 0 PASS / 4 FAIL / 2 UNMEASURABLE / 1 FAIL-LOW, and its post-mortem is baked into how these bands were built.

**Window type:** STABILITY. No MiWay service change is scheduled in this window. Predictions concern persistence of the v4/v5 findings.

## What the Sept-7 FINAL taught (applied up front, not discovered after)

1. **Bands centered on one week miss.** The Sept-7 pre-registration predicted the post-change world would look like the pre-change model output; it was wrong in every scoreable band. The v5 registration then centered bands on v4 alone and missed low on all three crowding metrics. Both failures have the same shape: one-week (or one-model-run) centers are too narrow for metrics with real daily spread. **This registration sets every band on the two-week observed range (v4 + v5) widened by that metric's known spread** — the same fix the Sept 21–27 registration introduced, retained here.
2. **"Stability" was the wrong prior for a changeover; persistence is the right prior for a calm window.** Two consecutive calm weeks (v5, and the pending v6) are now the basis class. The bands below predict *persistence of the v4→v5 level*, not continuation of any single week.
3. **The route-stability prior is retired for good.** v5's falsified "≥2 of {11, 66, 42, 103} repeat" was replaced in the Sept 21–27 registration by a reshuffle test; this registration does not re-adopt roster predictions at all. What the data supports is a *drift* claim, registered as band 1d below.
4. **Detector-vintage discipline.** The ghost band is only scoreable because the detector vintage is now stable across windows. If the ledger vintage changes inside this window, the ghost band is scored UNMEASURABLE with the vintage audit cited — pre-declared, so no one is tempted to score across vintages.
5. **Basis notes are pre-made, not improvised at freeze.** The equity/solver basis was superseded once already (Sept-7 FINAL: UNMEASURABLE-AS-REGISTERED). This registration contains no solver-output bands, so no basis-supersession failure mode can recur; feed-side bands use only metrics with stable definitions (FQ-10 early share, verifiable-trip ghost rate, raw-APC window-scoped crowding — same definitions as v4/v5, no basis mixing).

## Basis artifacts (two frozen weeks — v4 published 2026-09-14, v5 frozen 2026-09-21)

| Metric | v4 (Sept 7–13) | v5 (Sept 14–20) | Two-week read |
|---|---|---|---|
| Ghost trips (verifiable) | 121 of 30,848 (0.39%, 1-in-255) | 109 of 29,605 (0.37%, 1-in-272) | Regime ~0.35–0.40%, stable |
| Departures ≥2 min early (FQ-10) | 22.5% (n = 1,064,110) | 21.2% (n = 1,196,073) | Two-point drift down ~1.3 pt/wk |
| AM-peak early share | 26.4% (n = 113,929) | 26.0% (n = 127,887) | Flat (Δ0.4) |
| Route 2 late-night mean / SRO+ | 49% / 21.7% | 42% / 17.8% | Down, ±15-pt daily spread — weak trend evidence |
| Route 109 PM mean / SRO+ | 44% / 19.4% | 42% / 15.8% | Mean flat-ish; SRO+ bucket-granularity sensitive |
| Weekly measured departures | ~1.06M | 1.196M (incl. 1 partial day) | ~1.1–1.2M full-week expectation |

The Sept 21–27 window (v6, pending) closes *after* this registration is committed; by design none of its numbers are used here. If v6's frozen values shift the two-week read materially, the v7 *findings* document says so — this registration is never edited after commit.

## Predictions

### 1. Reliability

| # | Metric | Basis (v4→v5) | Predicted Sept 28–Oct 4 | Direction | Rationale |
|---|---|---|---|---|---|
| 1a | Ghost rate | 0.39% → 0.37% | **0.30–0.50%** (1-in-330 – 1-in-200) | ↔ | Two weeks in-regime with an unchanged timetable across the whole prediction span. Band = observed range ±0.05. Above 0.60% ⇒ regime shift, investigate before any civic claim; below 0.25% ⇒ suspected under-counting (collection regression), itself a finding. |
| 1b | Early share, all day | 22.5% → 21.2% | **19.0–22.5%** | ↔ / slight ↓ | The two-point downtrend is real but must not be extrapolated linearly: three weeks of ≤1.3 pt/wk drift lands ~19.9–21.2, and band edges allow a stall at the v5 level (21.2) or one more week of drift. Reaching ≥23.5% (v4's level back) falsifies the "new normal holds" reading; reaching v3's 26.3% ⇒ full reversion, a different civic story, published as such. |
| 1c | Early share, AM peak | 26.4% → 26.0% | **24.0–27.5%** | ↔ | Two weeks flat within 0.4 pt; AM-peak early departures are structural (dispatch behavior, not pad time), so the band centers on the flat read with spread room. |
| 1d | **Drift test** | v5 = 21.2% | **Weekly all-day early share ≤ 22.2%** (v5 + 1 pt) | ↔ | Replacement for the falsified roster prior: the falsifiable version of "the improvement holds." If the week's early share exceeds v5 + 1 pt, the post-change improvement is decaying and the civic materials must date their claims rather than quote a standing level. |

**Falsification (reliability):** 1a outside 0.25–0.60% fires its stated investigation clause, not a silent re-registration. 1b ≥23.5% and 1d >22.2% firing *together* means the drift reading was wrong in both directions considered — the v7 registration must state a new model, not widen these bands.

### 2. Night crowding (raw APC, window-scoped, uncorrected)

| # | Metric | Basis (v4→v5) | Predicted Sept 28–Oct 4 | Direction | Rationale |
|---|---|---|---|---|---|
| 2a | Route 2 late-night mean | 49% → 42% | **38–48%** | ↔ / slight ↓ | Band spans the honest uncertainty on a ±15-pt daily-spread metric (the exact mistake v5's 46–52 band made — set on v4 alone, missed low). Below 35% ⇒ the late-night pattern is dissolving, the civic claim is pulled entirely, not softened; above 52% ⇒ reversion to v4 levels, the "lull" reading wins. |
| 2b | Route 2 SRO+ | 21.7% → 17.8% | **14.5–21.5%** | ↔ / slight ↓ | Same logic; four-bucket APC granularity moves SRO+ in steps near thresholds. |
| 2c | Route 109 PM mean / SRO+ | 44% / 19.4% → 42% / 15.8% | **39–46% / 13.0–19.5%** | ↔ | Mean steady across two weeks; SRO+ band wide for bucket granularity. |

**Falsification (crowding):** any *single-week* verdict on 2a–2c is quoted with the pre-drafted fragility line (route-2 daily spread ±15 pt) — a band miss on route 2 without three consecutive same-direction days is a fragility note, not a retraction; the Sept-7 FINAL's route-2 FAIL is the precedent.

### 3. Collection health (guardrails, not findings)

| # | Metric | Basis | Predicted | Why it matters |
|---|---|---|---|---|
| 3a | Measured departures (week) | 1.06M → 1.196M | **1.05–1.30M** | Below 0.9M ⇒ collector stall (syncthing/cutover class); freeze delayed and flagged, same rule as v5/v6. |
| 3b | Complete days | 7/7, 6/7 | **7/7 by Wed Oct 7** | Missing day ⇒ caveat or delay, never a silent freeze. |
| 3c | Max collector gap (any day) | 11.4 h (Sept 19) | **<2 hours** | Guardrail introduced in the Sept 21–27 registration after the Sept-19 gap; retained. A >2 h gap ⇒ freeze carries a partial-day caveat AND the ops runbook gets an incident entry the same day. The watchdog + healthchecks.io stack (live since Sept 18) should make this unlikely; this band makes its failure visible. |

## Process commitments

1. **No post-hoc widening.** Bands frozen at commit time; a miss is published as a miss. The Sept-7 FINAL (0-for-4-FAIL) and v5 (3 FAIL-LOW) are the precedent — the ledger counts misses, and that is its entire authority.
2. **Freeze within 48 h of window close** (by Oct 7), pinned pipeline, SHA-256 manifest, same as v4/v5.
3. **Caveats at freeze, never after.** Partial days, gaps, and vintage notes go in the freeze manifest before publication.
4. **Verdict vocabulary:** PASS / FAIL-LOW / FAIL-HIGH / UNMEASURABLE (artifact cited). No partial credit, no "close enough."
5. **The route-stability prior stays retired.** Re-adopting it would require a written reason here; none is offered.
6. **If the detector vintage changes mid-window**, band 1a is UNMEASURABLE with the vintage audit cited — declared now so the scoring cannot be argued later.

---

*Committed before the window's data exists. GitHub commit timestamp is the witness. This document is never edited after commit; corrections happen in the v7 registration or a dated errata block in the v7 findings snapshot.*
