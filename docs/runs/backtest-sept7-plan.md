# Backtest plan — score the optimizer's pre-registered predictions against MiWay's actual Sept 7 change

**Status:** PLAN (owner-approved direction 2026-09-24; execution next session or on request)
**Question:** when the optimizer recommended re-timings before Sept 7, and MiWay then shipped its own Sept 7 change, how well did the recommendations and predictions survive contact with what actually happened?
**Why it matters (resume + MiWay thread):** converts "I built a tool" into "my tool made predictions about the world and I scored them." Also produces the one-page exhibit that would accompany an Oct 8 nudge if MiWay staff engage.

---

## 1. Inputs (all frozen; do NOT regenerate baselines)

| Input | Path | Notes |
|---|---|---|
| Pre-registration (7+ banded predictions, falsification criteria) | `docs/runs/pre-registration-sept7.md` (committed 2026-08-24, before first post-change capture) | the scoring contract |
| Pre-change GTFS baseline | `docs/sources/gtfs_archive/miway_gtfs_2026-08-23_pre-sept7.zip` (sha16 `f43fb0a9de891dbd`) | 26AU03-* service_ids |
| Post-change GTFS | SAME zip byte-identical — the changeover ships as the 26SE07-* service_id family inside one file (`docs/sources/gtfs_archive/MANIFEST.md`, manual protocol ruling 2026-09-11) | the comparison axis is service-id families, NOT zip files |
| Frozen post-change measurement weeks | `docs/runs/evidence-freeze-pre-sept7/` (pre) + findings v4/v5 (Sept 7–13, Sept 14–20 windows) | measured after-week |
| Already-scored prediction scorecard | `docs/email-drafts/FOLLOWUP-final-20260922.md` (0 passed / 4 failed / 2 unscoreable / 1 failed-low) | canonical Layer-A verdicts; re-derive, don't revise |
| Current optimizer basis | `docs/exec-summary.json` (2026-09-19 generation, basis service_date 20260911, `saved_pax_minutes` 9,714.6, `money.routes_moved` 42) | post-basis; the ROR post-Sept-7 rerun runbook exists (`docs/RUN-OF-RECORD.md:40,87`) if a like-for-like re-baseline is still owed |

## 2. Three scoring layers

### Layer A — prediction scorecard (mechanical re-derivation)
Re-derive each of the pre-registration's banded predictions from frozen artifacts and confirm or correct the follow-up email's verdicts. Rules: verdict = PASS / FAIL / UNSCOREABLE, no reinterpretation, artifact wins over prose. If a re-derivation contradicts the email's 0/4/2/1, report the discrepancy loudly instead of quietly improving the score.

### Layer B — recommendation-level backtest (the NEW axis)
1. **Harvest the optimizer's pre-change recommendations.** Preferred: locate the solver's shift rows for the pre-reg basis (equity-report.json move tables or a solver artifact; probe at execution). Fallback: re-run the solve on the pre-sept7 basis with the pre-reg's exact args (`--period all_day --volume-mode ridership --max-shift 5 --max-connections 6000 --time-limit 120`), exporting the shift table.
2. **Compute the actual change.** New small script (`backend/scripts/sept7_actual_change.py`): diff trips on 26AU03-* vs 26SE07-* per route — first-departure shifts and headway changes by daypart band. Output: table of routes MiWay actually re-timed.
3. **Match with pre-registered rules.** A recommendation (route, daypart, direction, magnitude bucket) MATCHES if MiWay changed that route in the same daypart with the same sign and magnitude within ±3 min (or headway within ±3 min). Changed-but-different = NEAR-MISS (counted, reported). Lock these thresholds before running.
4. **Score vs chance.** Hit-rate alone is meaningless without a baseline: compute the chance rate = (#routes MiWay changed) / (#routes in the optimizer's move universe, e.g. 42 moved of 67). Report lift = observed hit-rate / chance rate, with the caveat that both schedulers saw the same public timetable — convergence, not clairvoyance. MiWay's announcement named routes 8/66/43/109; report those separately from unannounced-route hits.
5. **Guardrail check:** pre-reg predicted the 45→109N acceleration transfer degrades <1 min and no Meadowvale pair degrades >2 min — verify against the measured after-week (`realized_waits` recompute / findings v4).

### Layer C — measured-wait band check
Score each pair-level band in pre-reg §2 against the frozen post-change realized waits (findings v4/v5, `daily_alert_join` rollups). **Vintage trap (logged in FOLLOWUP-template):** the harness's `realized_mean_min` for 313→43 is NaN; the pre-reg's 29.55 min / 0.952 missed is a DIFFERENT measurement vintage — name the vintage per row, never blend.

## 3. Exhibit spec (one page)

Deliverable: `docs/exhibits/backtest-sept7-onepager.md` (+ optional PDF via the existing Edge-headless render pipeline). Sections:
1. Verdict strip: scorecard (0/4/2/1) · recommendation lift vs chance · guardrails held/violated.
2. Three-layer table with a "what I got wrong" column (the two self-corrections + failed bands stay visible).
3. Provenance footer: every number → artifact path; CHECKED stamps from `check_claim.py` where geographic claims appear.
Audience: MiWay staff / councillor; tone: the follow-up email's — miss plainspoken, wins understated.

## 4. Execution order + estimate (~1 day total)

1. Locate/generate the post-basis exec-summary + equity artifacts per ROR runbook (~30 min incl. solve time).
2. `sept7_actual_change.py`: service-family diff + recommendation matcher with unit tests on synthetic two-family feeds (~2–3 h).
3. Layer A + C verdict tables from frozen artifacts (~1 h).
4. Exhibit generation (~1–2 h). Gates: ruff, new tests hermetic (`-m "not slow"`), no unregistered live solves.

## 5. Pre-registered integrity rules (locked now)

- No band edits after seeing post-change data (they were frozen 2026-08-24).
- Scoring rules (match/near-miss/chance-baseline) locked before running the matcher.
- The email's 0/4/2/1 is the canonical Layer-A score unless an artifact contradicts it; discrepancies are reported, never smoothed.
- Every exhibit number carries its artifact path; anything underivable is marked as such.
