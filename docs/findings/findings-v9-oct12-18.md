# Findings snapshot v9 — sixth post-change week (Oct 12–18)

> **FROZEN 2026-10-26 (backfilled).** This snapshot is immutable; corrections
> happen in a later snapshot or a dated erratum, never here. Every number
> below comes from the SHA-256 evidence freeze (the collection-wide v10 cut,
> frozen `2026-10-26T22:10Z`; manifest with per-file SHA-256s on file) via the
> pinned pipeline `derive_findings.py --start 2026-10-12 --end 2026-10-18
> --source freeze`.
>
> **Window caveats (declared at freeze, before publication):**
>
> 1. **Shared-cut pinning.** No as-of-close freeze exists for this window —
>    the freeze gate was unsatisfiable from 2026-10-05 until it was fixed on
>    2026-10-26, when the freeze ran as **v10**. These numbers are a window
>    slice of the v10 cut, frozen **8 days after this window closed**.
>    Date-keyed rows only; anything the collector rewrote between Oct 18 and
>    Oct 26 is here in its later form. A separate per-week corpus blob is
>    barred by the 2026-10-03 retention policy.
> 2. **The weakest ghost artifact of the three backfilled windows — since
>    repaired.** At freeze only **4 of 7 days** had any ghost rows at all:
>    Oct 13, 14 and 15 were absent entirely, and Oct 15's absence was not a
>    service gap (an ordinary weekday, with **204,898** observation rows of
>    its own). The tool's line — "10 of 2,653 verifiable trips never ran
>    (1 in 265) **over 4 days**" — was therefore a 4-day,
>    denominator-collapsed figure on ~**8%** of a healthy week's base, not
>    quotable and not comparable to v1–v7 (1 in 253 at v7). The cause was a
>    partial-day write; the absent days were backfilled the same day and the
>    rate is quotable again. Quote
>    [the erratum](erratum-2026-10-26-reliability-denominator.md) §4:
>    **93 ghosts / 31,117 verifiable of 31,219 scheduled = 0.30%
>    (1 in 335)**. The frozen table stands below as the artifact that was.
> 3. **Oct 12 runs holiday service.** Thanksgiving Monday: its **103,515**
>    observation rows and its **37** route rows in the ghost ledger are
>    holiday-shaped, not weekday-shaped — do not read the low Monday as a
>    service failure.
> 4. **Occupancy caveat:** the crowding artifact has no date column — those
>    figures are not this window's.
> 5. **Carry-forwards:** `ground_truth` and the `realized_waits` artifacts are
>    byte-identical to every earlier freeze, annotated as such in the
>    manifest.

---

## 1. Reliability

- Frozen artifact (do not quote as this window's rate): **10 of 2,653**
  verifiable trips over **4 days**, two of which are healthy — 1 in 265, on a
  denominator ~8% of a healthy week. Worst routes on the same caveat:
  **36 (2), 9 (2), 35 (2), 46 (1), 5 (1)**.
- **Quotable rate, re-derived 2026-10-26:** 93 ghosts / 31,117 verifiable of
  **31,219 scheduled** trips = **0.30% (1 in 335)** — the healthiest of the
  three repaired windows, and the arithmetic is trustworthy enough to say so.
  See the erratum for the repair and its residual caveats.
- **The frozen artifact, row for row** (published before the repair):

  | date | verifiable | ghosts |
  |---|---|---|
  | 20261012 | 2,050 | 9 |
  | 20261013 | *no rows* | — |
  | 20261014 | *no rows* | — |
  | 20261015 | *no rows* | — |
  | 20261016 | 303 | 0 |
  | 20261017 | 200 | 1 |
  | 20261018 | 100 | 0 |

## 2. Earliness (FQ-10 basis, forecast-cap era — never compare to v1–v3)

- Earliness: **23.5% of departures leave ≥2 min early** (n = 1,162,650);
  mean lateness **+0.06 min**.
- AM peak (07:00–09:00): **25.9% (n = 126,274) early**.
- Week series: all-day v6 22.1% → v7 22.8% → v8 22.6% → **v9 23.5%**; AM
  v6 26.3% → v7 28.8% → v8 28.7% → **v9 25.9%**. The all-day share drifts up
  ~0.9 pt while the AM share falls 2.9 pt — inside the week-to-week spread
  these series have shown (v6→v7 moved AM +2.5 pt), so the honest read is
  **no trend break**, and this is the one window in the chain whose AM figure
  includes a holiday Monday.
- Mean lateness **+0.06 min** is the closest to zero in the series (v7 +0.21,
  v8 +0.26), consistent with the lower AM early share. Not a service claim on
  one week.

## 3. Night crowding (raw APC signal, uncorrected — collection-wide aggregate)

- Route 109 (PM rush): mean **41%** full, worst decile ≥ **100%**, SRO+
  **16.3%** (n = 440,008).
- Route 2 (late night): mean **39%** full, worst decile ≥ **200%**, SRO+
  **16.0%** (n = 262,960).
- Route 5 (PM rush): mean **35%** full, worst decile ≥ **140%**, SRO+
  **8.5%** (n = 290,891).
- Routes averaging ≥33% full after 7 pm: **7** (126, 49, 2, 61, 66, 110, 109).

## 4. APC field audit

- Hand-counted check-ins: **399** across **14** routes (frozen methodology
  reference, not a weekly metric).

## 5. Collection health (this window)

- Datable days: **7 of 7** on the observation side — raw rows per day:
  103,515 (holiday) / 196,951 / 205,119 / 204,898 / 206,151 / 138,174 /
  107,842. 320,857 undated rows excluded, same rule as v2–v8.
- Collection itself was healthy; the **ghost recomputation** is what failed on
  Oct 13–15. Those days' observation data exists, which is exactly why their
  absence from the ledger was an artifact of the ghost pipeline, not of the
  collector.

## 6. Continuity against the registered Oct-26 bands (not a scored window)

- Pre-change week (the outgoing feed runs through 2026-10-25), so the
  registration does not score it — but the continuity read matters, because
  v9 is the mid-point of the baseline:

| Metric | v9 | Registered band | Position |
|---|---|---|---|
| Early share (all-day) | 23.5% | 21.0–24.5% | **inside**, closest to the ceiling of the three |
| AM-peak early share | 25.9% | 25–32% | **inside**, but only just — the holiday Monday sits in this window |
| Ghost rate | 0.30% (1 in 335) | 1-in-200 to 1-in-330 | **inside**, on the repaired denominator |

- The AM figure shows why the band was registered as a range rather than a
  point: a single holiday Monday moves it **2.8 pt** inside the envelope
  without the underlying behaviour moving.

## What changes in v10

- The ghost artifact degrades again: Oct 20 absent, Oct 21–25 all in the
  303/200/100 degenerate class, so the reliability rate stays unquotable until
  the repair.
- Earliness returns to the v7/v8 level (**22.5%** all-day, **28.1%** AM),
  which confirms v9's dip came with the holiday week rather than starting a
  trend.

## Footer

- **Frozen:** 2026-10-26 (backfilled from the v10 cut). This snapshot is
  immutable; it will never be edited.
- Supersession: superseded by [v10](findings-v10-oct19-25.md);
  [v8](findings-v8-oct5-11.md) was superseded by this snapshot.
- **Correction:** the reliability denominator was repaired 2026-10-26 —
  [the erratum](erratum-2026-10-26-reliability-denominator.md) supersedes this
  page's original "not quotable" banner.
