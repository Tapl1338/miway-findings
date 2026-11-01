# Findings snapshot v10 — seventh post-change week (Oct 19–25) — CURRENT

> **FROZEN 2026-10-26.** This snapshot is immutable; corrections happen in v11
> or a dated erratum, never here. Every number below comes from the SHA-256
> evidence freeze (`6 frozen, 0 skipped, 0 missing` at `2026-10-26T22:10Z`;
> manifest with per-file SHA-256s on file) via the pinned pipeline
> `derive_findings.py --start 2026-10-19 --end 2026-10-25 --source freeze`.
>
> **Window caveats (declared at freeze, before publication):**
>
> 1. **Collection-wide cut.** The v10 cut is a **collection-wide** snapshot
>    (374,704,674 B uncompressed observations), which is why v8 and v9 backfill
>    from it rather than each having a freeze of their own. The freeze chain had
>    been blocked since 2026-10-05, so this is the first on-time-in-intent
>    freeze since v7. Three artifacts are annotated byte-identical to earlier
>    windows in the manifest (written so the freeze is self-contained, not
>    independent measurements).
> 2. **The reliability denominator was broken — since repaired.** At freeze
>    this page said "do not quote the ghost rate", and that was correct then:
>    the ledger gave **23 of 5,531** verifiable trips over 6 days, with 21 of
>    the 23 ghosts concentrated on the one healthy day and the rest carrying a
>    degenerate constant ~**4.5** verifiable trips per route. Oct 20 was absent
>    from the ledger entirely while its observation data was present
>    (**205,031** rows) — an artifact of the ghost pipeline, not a service gap;
>    the frozen bytes matched the live file, so the freeze did not cause it.
>    The cause was a partial-day write plus a cursor that stepped past the
>    date, and it was repaired the same day (Oct 20 now has 67 rows). Quote
>    [the erratum](erratum-2026-10-26-reliability-denominator.md) §4:
>    **179 ghosts / 33,916 verifiable of 34,092 scheduled = 0.53%
>    (1 in 189)**. The frozen table stands below as the artifact that was.
> 3. **Earliness is on the normal basis.** ~205,000 deduped departures per
>    weekday, matching v6's complete days; the v7 window's thinner 756,644 is
>    reproduced exactly when re-derived from this cut, so the dedup rule has
>    not moved.
> 4. **Occupancy caveat:** collection-wide aggregate, no date column — the
>    crowding figures are not this window's.
> 5. **Carry-forwards:** `ground_truth` and the `realized_waits` artifacts are
>    byte-identical to prior freezes.

---

## 1. Reliability

- Frozen artifact (do not quote as this window's rate): **23 of 5,531**
  verifiable trips (1 in 240) over 6 days, denominator known-degenerate. Worst
  routes on the same caveat: **8 (4), 39 (4), 108 (2), 70 (2), 3 (2)**.
- **Quotable rate, re-derived 2026-10-26:** 179 ghosts / 33,916 verifiable of
  **34,092 scheduled** trips = **0.53% (1 in 189)** — the thinnest of the three
  repaired windows, which the erratum says plainly rather than as an
  improvement.
- **The frozen artifact, row for row** (published before the repair; "23 of
  5,531 over 6 days" is 21 ghosts on the one healthy day, and the rest carry
  the `303 / 200 / 100` degenerate class — ~**4.5** verifiable trips per
  route, against the **1 in 253** at v7 that it is *not* comparable to):

  | date | verifiable | ghosts |
  |---|---|---|
  | 20261019 | 4,323 | 21 |
  | 20261020 | *no rows* | — |
  | 20261021 | 303 | 2 |
  | 20261022 | 303 | 0 |
  | 20261023 | 303 | 0 |
  | 20261024 | 200 | 0 |
  | 20261025 | 99 | 0 |

- Concentration is real and unchanged: route 11 (37 ghosts over three weeks),
  110 (29), 126 (22, 2.24% of its own base), 39 (22), 22 (18), 74 (17, 3.80%),
  44 (17), 49 (17, 2.35%). Route 25, reported above as absent, is present for
  every date after the repair with 21 scheduled and 21 verifiable per weekday.

## 2. Earliness (FQ-10 basis, forecast-cap era — never compare to v1–v3)

- Earliness: **22.5% of departures leave ≥2 min early** (n = 1,250,469); mean
  lateness **+0.25 min**.
- AM peak (07:00–09:00): **28.1% (n = 140,592) early**.
- Week series: all-day v6 22.1% → v7 22.8% → v8 22.6% → v9 23.5% →
  **v10 22.5%**; AM v6 26.3% → v7 28.8% → v8 28.7% → v9 25.9% →
  **v10 28.1%**. The v9 dip reverted, so it reads as the holiday week rather
  than a trend. **Seven post-change weeks, flat at ~22.5% all-day and ~28% AM.**

## 3. Night crowding (raw APC signal, uncorrected — collection-wide aggregate)

- Route 109 (PM rush): mean **41%** full, worst decile ≥ **100%**, SRO+
  **16.3%** (n = 440,008).
- Route 2 (late night): mean **39%** full, worst decile ≥ **200%**, SRO+
  **16.0%** (n = 262,960).
- Route 5 (PM rush): mean **35%** full, worst decile ≥ **140%**, SRO+
  **8.5%** (n = 290,891).
- Routes averaging ≥33% full after 7 pm: **7** (126, 49, 2, 61, 66, 110, 109).
- Identical to v8/v9 — the same artifact point, so this is one measurement
  quoted three times, not three weeks of confirmation.

## 4. APC field audit

- Hand-counted check-ins: **399** across **14** routes — unchanged since v5.

## 5. Transfer timing (model, not measurement)

- Model-derived; the `realized_waits` artifacts are byte-identical to prior
  freezes and were not recomputed here.

## 6. Collection health (this window)

- Datable days: **7 of 7** — raw rows per day: 196,178 / 205,031 / 204,485 /
  203,650 / 202,654 / 132,471 / 106,000 (weekend taper on Oct 24–25).
  320,857 undated rows excluded, same rule as v2–v9.
- The analysis chain logged `failed=0/8` on every run that touched this window.
  The one genuinely failed step in the period was 2026-10-24T18:25
  (`failed=1/8`), re-run clean four minutes later at 18:29 — before this
  window's last day closed, so it does not touch these numbers.

## 7. This is the LAST pre-change week, and the baseline the first scored week is read against

- The feed boundary is exact: the outgoing feed runs through **2026-10-25** and
  the new one starts **2026-10-26** — the ~Oct-26 change the pre-registration
  was written for happened on schedule, and this window ends the day before
  it. So the **next** snapshot is the first post-change, band-scored week, and
  v10 is the last clean pre-change point.

| Metric | v10 | Registered band | Position |
|---|---|---|---|
| Early share (all-day) | 22.5% | 21.0–24.5% | **inside** |
| AM-peak early share | 28.1% | 25–32% | **inside** |
| Ghost rate | 0.53% (1 in 189) | 1-in-200 to 1-in-330 | **inside**, on the repaired denominator |

- The pre-change baseline for scoring: **all-day early 22.5–23.5% across
  v8–v10** (mean of the three ≈ 22.9%), **AM 25.9–28.7%**, and a ghost rate
  re-established at 0.30–0.53% over the three windows. Re-timing is the thing
  the Oct-26 change can move; the ghost rate is the thing it cannot, which is
  why the ghost band exists.

## Week-over-week summary

| Comparison | v8 (Oct 5–11) | v9 (Oct 12–18) | v10 (Oct 19–25) | Read |
|---|---|---|---|---|
| Ghost rate | 0.49% (1 in 204) | 0.30% (1 in 335) | **0.53% (1 in 189)** | repaired denominator; no regime change |
| Early share (all-day) | 22.6% | 23.5% | **22.5%** | flat; v9 carried the holiday |
| AM-peak early share | 28.7% | 25.9% | **28.1%** | flat at ~28% |
| Mean lateness | +0.26 min | +0.06 min | **+0.25 min** | flat |
| Route 109 PM SRO+ | 16.3% | 16.3% | 16.3% | one collection-wide measurement |
| After-7pm ≥33% routes | 7 | 7 | 7 | unchanged |

**Bottom line:** the earliness picture is stable across the three backfilled
weeks — 22.5–23.5% all-day, ~28% AM — so the version chain has no gap in the
metric that carries the re-timing argument. The reliability column now reads
0.30–0.53% (1 in 189 to 1 in 335) on a repaired denominator, inside the band
the pipeline produced before the damage: no October reliability regression, and
no improvement either.

## Footer

- **Frozen:** 2026-10-26. This snapshot is immutable; it will never be edited.
- Supersession: this is the current snapshot; [v9](findings-v9-oct12-18.md) is
  superseded.
- **Correction:** the reliability denominator was repaired 2026-10-26 —
  [the erratum](erratum-2026-10-26-reliability-denominator.md) supersedes
  §0.4's prohibition on this page.
