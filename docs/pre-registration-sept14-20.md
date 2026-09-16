# Pre-Registration: Week of Sept 14–20, 2026 (stability window)

**Committed:** 2026-09-16 (before any Sept 14–20 analysis; only 2 of 7 window days had elapsed)
**Status:** PRE-REGISTRATION — NEEDS-VERIFY by non-author handle
**Purpose:** Falsifiable week-over-week predictions for the Sept 14–20 collection window, committed before the window's data exists. This continues the practice started with [pre-registration-sept7.md](pre-registration-sept7.md): every weekly snapshot (v5 onward) gets a pre-registered comparison table, so the week-over-week story is hypothesis-driven, not post-hoc.

**Window type:** STABILITY. No MiWay service change is scheduled in this window (the Sept 7 quarterly change is the baseline; next change is not until the winter board). Predictions therefore concern *persistence and reversion* of the v4 findings, not change detection.

---

## Basis Artifacts (Frozen v4 Numbers — published 2026-09-14, never edited)

| Metric | v4 frozen value (Sept 7–13) | Source |
|---|---|---|
| Ghost trips | 121 of 30,848 verifiable (0.39%, "1 in 255") | `findings/findings-v4-post-sept7.md` §1 |
| Departures ≥2 min early | 22.5% (n = 1,064,110) | v4 §1 |
| AM-peak early share (07:00–09:00) | 26.4% (n = 113,929) | v4 §1 |
| Route 2 late-night load | mean 49% full; 21.7% SRO+ (n = 24,912) | v4 §2 |
| Route 109 PM-rush load | mean 44% full; 19.4% SRO+ (n = 38,272) | v4 §2 |
| Worst ghost routes | 11 (15), 66 (12), 42 (11), 103 (10) | v4 §1 |
| Weekly measured-departure volume | ~1.06M | v4 §1 n |

Comparison bases stay canonical: same metric definitions as v4 (ghost = verifiable-trip absence; early = ≥2 min before schedule; SRO+ = raw APC load ≥ seated capacity).

---

## Predictions

### 1. Reliability

| Metric | v4 (Sept 7–13) | Predicted Sept 14–20 | Direction | Rationale |
|---|---|---|---|---|
| Ghost rate | 0.39% (1/255) | **0.30–0.60%** (1/300 – 1/165) | ↔ stable | With the timetable unchanged, ghosts reflect vehicle/breakdown causes, not schedule drift. The changeover week's mismatches (dropped/stale trips) should not recur. |
| Early share (all day) | 22.5% | **21.0–25.0%** | ↔ / slight ↑ | v3→v4 dropped 26.3→22.5. First-week effects often partially revert as schedule padding gets consumed; a full revert to v3 levels is not expected. |
| Early share (AM peak) | 26.4% | **25.0–29.0%** | ↔ / slight ↑ | Same logic; AM peak reverts faster than all-day because dispatch pressure is highest there. |
| Top-5 ghost routes | 11, 66, 42, 103 lead | **≥2 of {11, 66, 42, 103} in the week's top 5** | ↔ | Ghost causes have proven route-specific (deadman/breakdown patterns follow vehicle assignments, which roll over weekly). |

**Falsification:** ghost rate >1.0% ⇒ a schedule/data mismatch is back (investigate before any civic claim); <0.15% ⇒ the detector is likely under-counting (collection regression), which is itself a finding.

### 2. Night crowding (raw APC, uncorrected)

| Metric | v4 | Predicted Sept 14–20 | Direction | Rationale |
|---|---|---|---|---|
| Route 2 late-night mean load | 49% | **46–52%** | ↔ | Two-week trend is upward (44→49) with no capacity or schedule relief added; persistence near v4 is the base case. |
| Route 2 SRO+ share | 21.7% | **19–24%** | ↔ | Same. |
| Route 109 PM mean / SRO+ | 44% / 19.4% | **41–47% / 16–22%** | ↔ | Express loads track school/commute patterns that are now in steady state post-change. |

**Falsification:** Route 2 mean <40% ⇒ the late-night pattern was changeover-specific (ridership distribution shifted back), which would soften the "night crowding is structural" claim — important to know BEFORE it goes in civic materials.

### 3. Collection health (guardrails, not findings)

| Metric | v4 | Predicted | Why it matters |
|---|---|---|---|
| Measured departures (week) | ~1.06M | **0.9–1.15M** | Below 0.7M ⇒ collector stall (syncthing/cutover class); freeze would be delayed and flagged, not published. |
| Complete days in window | 7/7 | **7/7 by Tue Sept 22** | A missing day shifts all rates' denominators; the freeze waits for completeness or carries a day-count caveat. |

---

## Process Commitments

1. **Freeze target:** Sun Sept 20 ~22:00 local, published as `findings-v5` (tag + immutable snapshot) once 7/7 days are COMPLETE.
2. **v5 opens with the v4→v5 comparison table filled from THESE ranges** — hit/miss recorded exactly as pre-registered, misses explained in place, no silent re-derivation to fit.
3. **Methodology unchanged:** any deviation (new calibration, different ghost scoring) must be declared in v5's methods section, and the affected comparisons re-based to v4's basis, not v5's.
4. If the window is NOT a stability week (emergency schedule change, major disruption), this registration is void and a fresh one is committed before analysis.

> Honest prior: this is the second registration. The Sept-7 registration scored well on direction but some ranges were wide. These ranges are tighter; if that produces misses, that is information, not failure.
