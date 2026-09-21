# Pre-Registration: Week of Sept 21–27, 2026 (second stability window)

**Committed:** 2026-09-21 (before any Sept 21–27 analysis; 0 of 7 window days complete)
**Status:** PRE-REGISTRATION — NEEDS-VERIFY by non-author handle
**Purpose:** Falsifiable week-over-week predictions for the Sept 21–27 collection window, committed before the window's data exists. Third in the series ([sept7](pre-registration-sept7.md), [sept14-20](pre-registration-sept14-20.md)). This is the first registration set with **two frozen weeks of basis** (v4 + v5), which changes how the bands are built: direction and drift get evidence, not just a point estimate.

**Window type:** STABILITY. No MiWay service change is scheduled in this window. Predictions concern persistence of the v4/v5 findings.

**What the two-week basis changes (stated up front):**

1. **Bands are set on the two-week range, widened by observed spread, not centered on last week.** v5 taught this the hard way: bands centered on v4 alone missed low on every crowding metric. The registered bands below are deliberately wider where the daily spread is known to be large (Route 2 late-night: ±15-pt daily swing) and narrower where two weeks agree closely (ghost rate: 0.39% → 0.37%).
2. **The week-over-week route-stability prior is retired.** The v5 registration predicted ≥2 of {11, 66, 42, 103} would repeat in the top-5 ghost routes; only 11 did. Two weeks of data show the roster reshuffles. This registration replaces that prediction class with a testable version of what the data actually supports (see 1d).
3. **Collector continuity becomes a registered guardrail.** The Sept 19 collector gap (01:28–12:54 EDT) was discovered at freeze. A gap of that size is preventable at the guardrail level, so it is now a pre-registered health check (see 3c).

---

## Basis Artifacts (two frozen weeks — v4 published 2026-09-14, v5 frozen 2026-09-21, never edited)

| Metric | v4 (Sept 7–13) | v5 (Sept 14–20) | Two-week read |
|---|---|---|---|
| Ghost trips (verifiable) | 121 of 30,848 (0.39%, 1-in-255) | 109 of 29,605 (0.37%, 1-in-272) | Regime ~0.35–0.40%, stable |
| Departures ≥2 min early | 22.5% (n = 1,064,110) | 21.2% (n = 1,196,073) | Drifting down ~1.3 pt/wk |
| AM-peak early share | 26.4% (n = 113,929) | 26.0% (n = 127,887) | Flat (Δ0.4) |
| Route 2 late-night mean / SRO+ | 49% / 21.7% | 42% / 17.8% | Down, but daily spread ±15-pt makes the trend weak evidence |
| Route 109 PM mean / SRO+ | 44% / 19.4% | 42% / 15.8% | Mean flat-ish; SRO+ down 3.6 (bucket-granularity sensitive) |
| Worst ghost routes | 11 (15), 66 (12), 42 (11), 103 (10) | 61 (23), 11 (16), 28 (16), 110 (10), 5 (10) | Only 11 repeats — roster is NOT stable |
| Weekly measured departures | ~1.06M | 1.196M (incl. 1 partial day) | ~1.1–1.2M full-week expectation |

Comparison bases stay canonical: same metric definitions as v4/v5 (ghost = verifiable-trip absence; early = ≥2 min before schedule; SRO+ = raw APC load ≥ seated capacity). No basis mixing.

---

## Predictions

### 1. Reliability

| # | Metric | Basis (v4→v5) | Predicted Sept 21–27 | Direction | Rationale |
|---|---|---|---|---|---|
| 1a | Ghost rate | 0.39% → 0.37% | **0.30–0.50%** (1-in-330 – 1-in-200) | ↔ | Two weeks in-regime with an unchanged timetable. Band tightened to the observed range ±0.05 — if this misses, something actually changed. |
| 1b | Early share (all day) | 22.5% → 21.2% | **20.0–23.5%** | ↔ / slight ↓ | Two-point downtrend; if the drift is real, expect ≤21.5. Full reversion to v3 levels (>25%) would falsify the "new normal" reading. |
| 1c | Early share (AM peak) | 26.4% → 26.0% | **24.5–28.0%** | ↔ | Two weeks flat within 0.4 pt; AM-peak pressure is structural (dispatch, not padding). |
| 1d | Ghost-route recurrence | Only 11/15 in both top-5s | **≥1 of {61, 11} in the week's top 5, AND no more than 2 of v5's top 5 repeat** | weak ↔ | Replacement for the falsified stability prior. Routes 61 and 11 have two-week recurrence (28 does not — one-week blip). The "no more than 2 repeat" clause tests the reshuffle finding: 3+ repeats would mean v5's reshuffle was itself the fluke. |

**Falsification:** ghost rate >0.60% ⇒ regime shift — investigate before any civic claim; <0.25% ⇒ detector under-counting (collection regression), itself a finding. If 1d fails in BOTH clauses (61 and 11 absent AND ≥3 of v5's top 5 repeat), the reshuffle conclusion is wrong and the stability prior comes back for v7.

### 2. Night crowding (raw APC, uncorrected)

| # | Metric | Basis (v4→v5) | Predicted Sept 21–27 | Direction | Rationale |
|---|---|---|---|---|---|
| 2a | Route 2 late-night mean | 49% → 42% | **38–48%** | ↔ / slight ↓ | Two-point downtrend, but a ±3-pt band on a metric with ±15-pt daily spread was v5's mistake; this band spans the honest uncertainty. |
| 2b | Route 2 SRO+ | 21.7% → 17.8% | **14.5–21.5%** | ↔ / slight ↓ | Same logic; four-bucket granularity moves SRO+ in steps near thresholds. |
| 2c | Route 109 PM mean / SRO+ | 44%/19.4% → 42%/15.8% | **39–46% / 13.0–19.5%** | ↔ | Mean steady; SRO+ band wide because bucket granularity makes small shifts lumpy. |

**Falsification:** Route 2 mean <35% ⇒ the late-night pattern is dissolving (not just changeover-specific) — the civic-materials claim must be pulled entirely, not softened. Above 52% ⇒ reversion to v4 levels; the "second week was a lull" reading wins.

### 3. Collection health (guardrails, not findings)

| # | Metric | Basis | Predicted | Why it matters |
|---|---|---|---|---|
| 3a | Measured departures (week) | 1.06M → 1.196M | **1.05–1.30M** | Below 0.9M ⇒ collector stall (syncthing/cutover class); freeze delayed and flagged. |
| 3b | Complete days | 7/7 (v4), 6/7 (v5) | **7/7 by Tue Sept 29** | Missing day ⇒ caveat or delay, same rule as v5. |
| 3c | **Max collector gap (any day)** | 11.4h (Sept 19) | **<2 hours** | NEW guardrail, registered in response to the Sept-19 gap. A gap >2h ⇒ the freeze carries a partial-day caveat AND the ops runbook gets an incident entry the same day. The watchdog/healthcheck stack (added Sept 18) should make >2h unlikely; this registration makes its failure visible. |

---

## Process Commitments

1. **No post-hoc widening.** The bands above are frozen at commit time. A miss is a miss and gets published as one — that is the entire credibility mechanism. (v5 scored 3 FAIL-LOW and published them; the direction of the misses is part of the record.)
2. **Freeze within 48h of window close** (by Sept 29), using the pinned pipeline and a SHA-256 manifest, same as v5.
3. **Caveats at freeze, never after.** Any partial day, gap, or artifact-vintage note is declared in the freeze manifest before publication.
4. **Verdict vocabulary:** PASS (inside band) / FAIL-LOW / FAIL-HIGH (outside, direction named) / UNMEASURABLE (no like-for-like basis, artifact cited). No partial credit.
5. **The route-stability prior stays retired** unless 1d's dual failure explicitly revives it. Re-adopting a falsified prior requires a written reason in the v7 registration.

---

*Committed before the window's data exists. GitHub commit timestamp is the witness. The comparison table in findings-v6 is filled from the frozen cut only, and this document is never edited after commit (corrections happen in the v7 registration or an errata block in v6's snapshot).*
