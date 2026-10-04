# FQ-8 verdict — "wins 100% of 500 days" Monte Carlo audit

**Auditor:** Buffy (falsifier seat, on behalf of the FQ-8 pre-registered attack)
**Date:** 2026-08-30
**Target claim:** "The re-timed plan wins on 100% of simulated days" (Monte Carlo driven by observed lateness).
**Trigger:** before next quote of the win-probability number.

## 1. What the artifact actually carries

`docs/validation-study.json` (HEAD = `c790f60`, 2026-08-24 "T07 closed"):

- `monte_carlo[0]` (validation-study.json → `monte_carlo`):
  - `lateness_model`: "observed AVL/GTFS-RT bootstrap (338,667 departures)"
  - `simulated_days`: 500
  - `mean_savings_minutes`: 785.3 · `median_savings_minutes`: 784.6
  - `p5_savings_minutes`: **696.6** · `p95_savings_minutes`: **876.3**
  - `pct_days_optimized_wins`: **100.0**
  - `pct_days_beats_paper`: **0.0** (realized gain never matches the deterministic paper gain on any simulated day — the honest counterweight to "100%")
- `realtime.summary.observed_departures`: 338,667
- `period`: PM Rush (matches the "PM rush" prose).

**FQ-8 checklist:**

| Attack item | Verdict |
|---|---|
| JSON carries the actual distribution | **PARTIAL** — carries the distribution *summary* (mean/median/p5/p95/wins%), **not the raw 500-day array**. Reproducible via pinned seed `np.random.default_rng(20240813)` (validation_study.py:329) — same seed → same numbers. |
| p5/p95 exist | **YES** — p5 696.6, p95 876.3 (validation_study.py:168-169). |
| Basis: 338,667 departures | **YES** — in the model label + `realtime.summary.observed_departures`. |
| Basis: dated (regen date) | **NO** — the JSON has **no timestamp/regen-date field**; `generated_with` names the command, not the date. The regen date lives only in git (`c790f60`, 2026-08-24) and `docs/runs/T17-sweep.md:16` ("regenerated 2026-08-24 13:02"). The prose "Aug 17-23" date range is also **not in the artifact** — it is prose-added (dated obs_lateness rows only begin 2026-08-23; the legacy/undated block is pre-date-column). |

**Statistical plausibility:** p5 = +696.6 min/day ≫ 0, so a 100% win rate is entirely expected — the whole distribution sits far above zero. "100%" here means *beats today's schedule every simulated day*, not *matches the paper gain* (`pct_days_beats_paper` = 0.0). The claim is not "suspiciously perfect"; it is an artifact-supported, well-grounded number.

## 2. Prose claims vs the current artifact

Current artifact truth: **338,667 departures · 500 days · wins 100.0% · median +785 · p5 696.6 · p95 876.3 · PM rush**.

| Location | Quote | Verdict |
|---|---|---|
| `SUMMARY.md:18` | "338,667 … (PM rush) … wins on 100% of simulated days" | **HOLDS** — matches artifact exactly. |
| `docs/RUN-OF-RECORD.md:21` | "338,667 departures, wins 100% of 500 days, median +785 net min/day" | **HOLDS** — matches exactly. |
| `docs/council-motion.md:34` | "100% of 500 simulated days (median +785 …)" | **HOLDS** — matches exactly. |
| `docs/councillor-qa.md:49` | "338,667 observed departures, Aug 17-23 bootstrap … 100%" (continues :51 "most days, not every day…") | **FLAG (self-contradiction)** — the 100% matches, but the contiguous "most days, not every day" hedge (:51) is a leftover from the 74% era; "Aug 17-23" is prose-added, not in the artifact (minor). |
| `docs/ward-9-motion.md:39-40` | "wins on 100% of simulated days" | **HOLDS** (no numbers attached). |
| **`docs/README.md:108`** | "the real-data Monte Carlo still wins most (**74%**) of simulated days" | **BREAKS (stale)** — same old `3720b62` figure as exec-summary; current artifact: 100%. |
| `docs/what-the-tool-finds.md:97` | "wins on 100% of simulated days … median +785" | **HOLDS** — matches exactly. |
| `docs/pitch-and-qa.md:11` | "won on 100% of simulated days — all 500 of them" | **HOLDS** — matches exactly. |
| **`docs/ward-9-brief.md:46`** | "wins on **100%** … (median +785 min saved/day, **p5 −10.5**, p95 +876)" | **BREAKS (mixed vintage)** — p5 **−10.5** is from the OLD 50-day run (`3720b62`: p5 −10.5, p95 20.0, 205,109 departures, 74% wins), not the current artifact (p5 **+696.6**, p95 876.3). Median/p95/100% are current; the p5 is stale. Must be corrected to +696.6 before next quote. |
| **`docs/exec-summary.md:45`** | "wins on **74% of simulated days (50 simulated days)**" | **BREAKS (stale)** — the 74%/50-day figure is the old `3720b62` vintage (205,109 departures). Current artifact: 100% of 500 days. Also "~9.75 min late" elsewhere conflicts with the 12+ min wording in the briefs. |
| **`docs/demo-video-script.md:39`** | "163,000 observed MiWay departures … **75% of simulated operating days**" | **BREAKS (unverifiable)** — 163,000/75% matches **no committed artifact vintage** (36,142 / 107,187 / 205,109 / 338,667; wins 74.0 or 100.0). |
| **`docs/project-writeup.md:9`** | "163,000 real observed MiWay departures … **75% of simulated operating days**" | **BREAKS (unverifiable)** — same as above. |
| **`docs/pitch-and-qa.md:29`** | "Monte Carlo driven by **107,000** real observed MiWay departures … wins on 100% of days" | **BREAKS (stale count)** — 107,000 matches the `89871ef` vintage (107,187). Current basis is 338,667; the 100% itself still holds. Also "6 minutes late" conflicts with the 12+ min figure used elsewhere. |
| **`docs/councillor-brief.md:68`** | "wins on **100% of simulated days** … — most days, not every day, and the reports say so." | **FLAG (self-contradiction)** — "100%" then "most days, not every day": the hedge is a leftover from the 74% era. With 100% it should read "every simulated day" (with the honest counterweight: it never matches the paper gain). |
| **`docs/what-the-tool-finds.md:22`** | "wins on 100% of simulated days — most days, not every day." | **FLAG (self-contradiction)** — same leftover hedge. |
| `docs/runs/run-b/exec-summary.md:45` | "74% … (50 simulated days)" | ARCHIVED FOSSIL (run-b is the documented pre-rebasis run; T01). Leave as-is, never re-quote. |

## 3. Verdict

**HOLDS with caveats — but 5 prose locations must be fixed before the next quote (ward-9-brief p5, exec-summary 74%, README 74%, demo-video-script 163k/75%, project-writeup 163k/75%, pitch-and-qa 107k), and 3 more are self-contradictory (councillor-brief, what-the-tool-finds, councillor-qa hedges).**

The artifact genuinely supports "wins on 100% of 500 simulated days (PM rush, 338,667 observed departures, median +785, p5/p95 696.6/876.3)" — the number is real, reproducible (pinned seed), and statistically expected given p5 ≫ 0. It is *not* the "suspiciously perfect" overstatement FQ-8 was hunting: the same JSON honestly reports `pct_days_beats_paper = 0.0`.

**Required before next public quote (FQ-8 / FQ-10 discipline):**

1. `docs/ward-9-brief.md:46` — replace "p5 −10.5" with "p5 +697" (artifact p5 696.6). Mixed-vintage citation is the exact error class FQ-8 exists for.
2. `docs/exec-summary.md:45` **and `docs/README.md:108`** — replace "74% of simulated days (50 simulated days)" / "most (74%)" with "100% of 500 simulated days" (or re-run and re-quote the current artifact).
3. `docs/demo-video-script.md:39` + `docs/project-writeup.md:9` — 163,000/75% matches no artifact; either re-run to a committed basis or delete the numbers.
4. `docs/pitch-and-qa.md:29` — update "107,000 departures" → "338,667 departures"; reconcile "6 minutes late" → the 12+ min figure.
5. `docs/councillor-brief.md:68` + `docs/what-the-tool-finds.md:22` **+ `docs/councillor-qa.md:51`** — resolve the "100% … most days, not every day" contradiction (say "every simulated day" or quote the 0% beats-paper honestly).

**Artifact gap (not blocking, but FQ-10):** validation-study.json carries no regen timestamp. Recommend stamping `generated_at` (UTC) + the obs_lateness input hash at write time so the "dated basis" lives in the artifact, not in git archaeology. The raw per-day savings array could also be persisted (small; makes the 100% directly re-auditable without a re-run).

## 4. Companion deep sweep — the same mixed-vintage disease, other generators

Beyond the Monte Carlo claim, the sweep checked the other quoted-stat artifacts
(`exec-summary.json`, `equity-report.json`, `validation-report.json`) against
prose. Canonical current truth these were checked against:

- **saved pax-min/day:** exec-summary.json `result.saved_pax_minutes` = **9,737.7** (all-day, ridership, 6,000 conns, `--time-limit 120`); validation-report.json `result.saved_pax_minutes` = 4,731.0 (its own smaller basis).
- **sensitivity trio:** exec-summary.json = **+10,316 / +6,529 / +3,904** (mu 1/2/3); validation-report.json = +4,280 / +2,867 / +1,862 (mu 1/2/3) — two distinct correct bases, must not be blended.
- **flip:** exec-summary.json `flip_threshold` = **9.75**; validation-report.json `flip` = `{threshold_min: None, tested_to: 12.0}` (did not observe a flip by 12 min). So "9.75" (exec-summary) and "12+" (validation-report / briefs) are **both artifact-accurate to their own generator** — an honest difference, not a stale-vintage error.
- **equity, Ward 9:** equity-report.json `wards.rows[ward=9]` = **21 stops, +2.56 min, 15 worse-off stops, proxy 215,556**. Citywide worse-off-stops sum (11 wards, 262 stops) = **172**.

| Location | Quote | Verdict |
|---|---|---|
| `docs/council-motion.md:26` | "approximately **3,400** passenger-minutes … that can be saved per weekday" | **BREAKS (stale run)** — 3,400 is the old uncapped/older pin; exec-summary.json current = **9,737.7**. The motion's own header (:13) says "generated 2026-08-22". |
| `docs/ward-9-motion.md:19` | "finds approximately **3,400** passenger-minutes … saved" | **BREAKS (stale run)** — same; current = 9,737.7. |
| `docs/pitch-and-qa.md:9` | "the tool finds roughly **3,400** passenger-minutes … saved per day" | **BREAKS (stale run)** — same; current = 9,737.7. |
| `docs/council-motion.md:43` | "**20 worse-off stops** citywide" | **BREAKS (unverifiable)** — equity-report.json sums to **172** worse-off stops (vintage range 34–175 across git history; none equals 20). |
| `docs/councillor-qa.md:29` | "**20 stops** citywide are projected worse-off" | **BREAKS (unverifiable)** — identical 20-vs-172 mismatch. |
| `docs/ward-9-motion.md:26` | "Ward 9 … **10 of its 15 measured transfer stops see longer waits**, averaging **+2.60 min**" | **BREAKS (stale)** — equity-report.json says 21 stops, **15 worse-off**, **+2.56 min**; ROR:33 already records the DEC-07 correction ("10 of 21" was a transcription slip; correct = 6 ahead / 15 worse of 21). Ward-9-brief:18 already has the correct 15 / +2.56. Motion not resynced. |
| `docs/ward-9-brief.md:41` | "+4,280 … +2,867 … +1,862" (mu 1/2/3) | **HOLDS** — matches validation-report.json sensitivity (4,279.9 / 2,867.4 / 1,861.8), its own basis. Note: this is the validation-report basis, distinct from exec-summary's +10,316 trio; both correct, keep the families apart. |
| `docs/exec-summary.md:45` "~**9.75 min late**" | **HOLDS** — exec-summary.json `flip_threshold` = 9.75 exactly. (Earlier note calling this a conflict is retracted; the "12+" lives in validation-report's flip and is its own correct basis.) |
| `docs/councillor-brief.md:36` | "agree at 9,737.7 vs 9,737.6 … ~3,400 … do not mix vintages" | **HOLDS** — this doc already narrates the 3,400-to-9,737 drift as the caution, not a live quote. |

**Deep-sweep verdict:** 6 more BREAKS (3× `3,400`, 2× `20 worse-off stops`, 1× Ward-9 `10-of-15/+2.60`), all tracing to the pre-rebasis 2026-08-22 run or an unverifiable count. The motions (`council-motion.md`, `ward-9-motion.md`) and `pitch-and-qa.md` were left on the old pin; the briefs and exec-summary were resynced and are internally consistent. Same root cause and same fix family as the MC quotes.

## 5. Method / evidence

- Artifact read: `docs/validation-study.json` (`monte_carlo[0]`, `realtime.summary`, `generated_with`).
- Generator: `backend/scripts/validation_study.py` — MC block built at :163-174 (`p5/p95` :168-169, wins :170, beats-paper :171); seed pinned :329; no raw array persisted (return dict :163-176).
- Vintage archaeology: `git log --all -- docs/validation-study.json` → `c790f60` (338,667/500/100.0/p5 696.6), `3720b62` (205,109/50/74.0/p5 −10.5), `89871ef` (107,187/500/100.0/p5 3638.9), `f007a65` (36,142/500/100.0), `36cef4b`/`d0a2f84` (32,704/500/100.0), `28cf926` (32,704/500/99.6), `84b795b` (parametric 57.0/76.4).
- Prose sweep: `grep -rn "100%|500 days|wins on|Monte Carlo" docs/ --include="*.md"`; every hit read in context and diffed against the artifact truth row above.
- No files modified; no regeneration performed. This receipt is the deliverable.
