# Pre-Registration: Week of Sept 21–27, 2026 (stability window, second repeat)

**Committed:** 2026-09-16 (before any Sept 21–27 analysis; only 0 of 7 window days had elapsed — the *earliest* registration yet, two full days before the previous window even closed)
**Status:** PRE-REGISTRATION — NEEDS-VERIFY by non-author handle
**Purpose:** Continues the practice (pre-registration-sept7, -sept14-20): every weekly snapshot gets a pre-registered comparison table committed before the window's data exists.

**Window type:** STABILITY II. No service change scheduled; next change is the winter board. Predictions concern persistence of the v4-era findings across a second unchanged week.

**Basis caveat (honest, stated up front):** the natural basis would be v5's frozen numbers (Sept 14–20), but v5 will not be frozen until ~Sept 22 — *after* this registration's commit. This registration therefore predicts **from v4's frozen values** (published 2026-09-14, never edited) with bands wide enough to absorb one week of drift; v5's realized values will be checked against v4's bands at the v5 freeze, and this window's data will be scored against v4 bands + the v5 realization both. Predicting two-weeks-persistent from the same frozen basis is *more* falsifiable, not less: if v5 drifted materially, the v5 freeze itself falsifies these bands before the window opens.

## Basis Artifacts (Frozen v4 Numbers — published 2026-09-14, never edited)

| Metric | v4 frozen value (Sept 7–13) | Source |
|---|---|---|
| Ghost trips | 121 of 30,848 verifiable (0.39%, "1 in 255") | `findings/findings-v4-post-sept7.md` §1 |
| Departures ≥2 min early | 22.5% (n = 1,064,110) | v4 §1 |
| AM-peak early share (07:00–09:00) | 26.4% (n = 113,929) | v4 §1 |
| Route 2 late-night load | mean 49% full; 21.7% SRO+ (n = 24,912) | v4 §2 |
| Route 109 PM-rush load | mean 44% full; 19.4% SRO+ (n = 38,272) | v4 §2 |
| Weekly measured-departure volume | ~1.06M | v4 §1 n |

## Predictions

### 1. Reliability

| Metric | v4 basis | Predicted Sept 21–27 | Direction | Rationale |
|---|---|---|---|---|
| Ghost rate | 0.39% | **0.25–0.60%** | ↔ | Timetable unchanged 3rd week; ghost causes are vehicle/operational, not schedule drift. Wider low end than the sept14-20 registration (0.30) to absorb one extra week of vehicle-assignment churn. |
| Early share (all day) | 22.5% | **20.0–25.5%** | ↔ | First-week padding consumed by week 3; expect slow reversion upward toward v3's 26.3 but not reaching it. |
| Early share (AM peak) | 26.4% | **24.0–29.5%** | ↔ | AM peak reverts fastest (dispatch pressure); band widened accordingly. |

**Falsification:** ghost rate >1.0% ⇒ schedule/data mismatch returned (investigate before civic claims); <0.15% ⇒ detector under-counting (collection regression — itself a finding). Early share ≥ v3's 26.3% all-day ⇒ the post-change improvement has fully reverted within 3 weeks — a materially different civic story than "sustained improvement."

### 2. Night crowding (raw APC, uncorrected)

| Metric | v4 basis | Predicted Sept 21–27 | Direction | Rationale |
|---|---|---|---|---|
| Route 2 late-night mean load | 49% | **44–53%** | ↔ | Two-week upward trend (44→49) may continue; band asymmetric upward. |
| Route 2 SRO+ share | 21.7% | **17–25%** | ↔ | Tracks mean. |
| Route 109 PM mean / SRO+ | 44% / 19.4% | **40–48% / 15–23%** | ↔ | Express loads steady-state post-change. |

**Falsification:** Route 2 mean <40% ⇒ the late-night crowding pattern was changeover-specific, not structural — softens the civic claim BEFORE it reaches any materials.

### 3. Collection health (guardrails, not findings)

| Metric | v4 basis | Predicted | Why it matters |
|---|---|---|---|
| Measured departures (week) | ~1.06M | **0.9–1.15M** | Below 0.7M ⇒ collector stall class; freeze delayed, not published. |
| Complete days in window | 7/7 | **7/7 by Tue Sept 29** | Missing day ⇒ day-count caveat or delayed freeze. |
| Sept-22 scorecard | — | runs FINAL (≥10 weekdays: 7 collected through Sept 16 + Sept 17/18/21) | The pre-registered Sept-7 verdict lands this window; it is scored against its OWN registration, not this one. |

## Process Commitments

1. Scoring happens only against the frozen evidence cut, by the pinned pipeline — never live CSVs, never memory.
2. Verdict vocabulary fixed in advance: PASS / FAIL-LOW / FAIL-HIGH / UNMEASURABLE (with artifact citation). No "close enough."
3. Every refutation is published in v6 as-is. The scorecard's authority comes from publishing its own misses.
4. Guardrail breaches (collection health) delay the freeze; they are never silently absorbed.
