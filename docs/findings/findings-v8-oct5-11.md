# Findings snapshot v8 — fifth post-change week (Oct 5–11)

> **FROZEN 2026-10-26 (backfilled).** This snapshot is immutable; corrections
> happen in a later snapshot or a dated erratum, never here. Every number
> below comes from the SHA-256 evidence freeze (the collection-wide v10 cut,
> frozen `2026-10-26T22:10Z`; manifest with per-file SHA-256s on file) via the
> pinned pipeline `derive_findings.py --start 2026-10-05 --end 2026-10-11
> --source freeze`.
>
> **Window caveats (declared at freeze, before publication):**
>
> 1. **Shared-cut pinning.** No as-of-close freeze exists for this window: the
>    freeze gate was unsatisfiable from 2026-10-05 to 2026-10-26 (its
>    precondition never matched the chain's success line), so the freeze ran
>    as **v10** and this window is a slice of that cut — frozen **15 days
>    after this window closed**. Observations and the ghost ledger are
>    date-keyed, so the slice is byte-pinned, but it is *the state of those
>    rows on Oct 26*, not on Oct 11. A per-week corpus blob would have cost
>    another 87 MB for byte-identical content and is barred by the 2026-10-03
>    retention policy (the raw corpus does not go into git). One cut, three
>    windows, stated plainly, is the trade taken.
> 2. **The reliability denominator was broken — since repaired.** At freeze
>    this snapshot carried "do not quote the ghost rate", and that was correct
>    *then*: the ghost ledger was degenerate on 6 of 7 days, with the tell-tale
>    constants **303 / 200 / 100** verifiable trips per day — a computation
>    signature, not a service signature (a normal weekday verifies ~4,300
>    trips; v7 held 22,492 over 7 days, here 4,380 on Oct 5 alone). The
>    artifact value was 52 of 5,892 "verifiable" trips (1 in 113), and 51 of
>    those 52 ghosts sat on the single healthy day. Read the rate from
>    [the erratum](erratum-2026-10-26-reliability-denominator.md) §4, not from
>    that artifact: **161 ghosts over 32,782 verifiable trips = 0.49%
>    (1 in 204)**. The frozen table stands below as the artifact that was.
> 3. **Earliness n is the normal basis.** v7's 756,644 deduped departures was
>    a thin-collection figure; October weekdays here dedup to ~205,000,
>    matching v6's 188–204k complete days. Re-deduping the v7 window from this
>    same cut reproduces its 756,644 exactly, so the dedup rule is unchanged
>    and the early *share* is directly comparable across v7→v8.
> 4. **Occupancy caveat (every snapshot):** the crowding artifact has no date
>    column. Those figures cover the whole collection period as of the
>    artifact point, **not** this window.
> 5. **Carry-forwards:** `ground_truth` and the `realized_waits` artifacts in
>    this cut are byte-identical to every earlier freeze (annotated in the
>    manifest) — written so the freeze is self-contained, not independent new
>    measurements.

---

## 1. Reliability

- The frozen artifact (do not quote as this window's rate): 52 of 5,892
  "verifiable" trips never ran (1 in 113) over 7 days, denominator
  known-degenerate — **not comparable to v1–v7 (1 in 253 at v7)**. Worst
  routes on the same caveat: **17 (8), 109 (7), 2 (4), 5 (4), 11 (4)**.
- **Quotable rate, re-derived 2026-10-26:** 161 ghosts / 32,782 verifiable of
  **34,092 scheduled** trips = **0.49% (1 in 204)**. Oct 5 is the one date
  whose denominator is still a floor (4,380, **78.4%** of its scheduled trips):
  its 51 ghosts over the smaller base read 1.16% where the true rate is
  ~0.9%, so this window's rate is marginally *pessimistic* rather than
  flattering. See the erratum for the repair and its residual caveats.
- **The frozen artifact, row for row** (this is the table that was published
  before the repair, and the one the erratum quotes as "the artifact that
  was"): the repeated `303 / 200 / 100` totals are a constant ~**4.5**
  verifiable trips per route regardless of date.

  | date | verifiable | ghosts |
  |---|---|---|
  | 20261005 | 4,380 | 51 |
  | 20261006 | 303 | 1 |
  | 20261007 | 303 | 0 |
  | 20261008 | 303 | 0 |
  | 20261009 | 303 | 0 |
  | 20261010 | 200 | 0 |
  | 20261011 | 100 | 0 |

## 2. Earliness (FQ-10 basis, forecast-cap era — never compare to v1–v3)

- Earliness: **22.6% of departures leave ≥2 min early** (n = 1,195,239);
  mean lateness **+0.26 min**.
- AM peak (07:00–09:00): **28.7% (n = 141,287) early**.
- Week series, all-day early share on the same basis: v5 21.2% → v6 22.1% →
  v7 22.8% → **v8 22.6%**. AM: v5 26.0% → v6 26.3% → v7 28.8% →
  **v8 28.7%**. Flat. The post-change gain holds; the AM level set at v7 is
  reproduced, not eroded.

## 3. Night crowding (raw APC signal, uncorrected — collection-wide aggregate)

- *No date column, so these cover the whole collection period as of the
  freeze point, not this window. The n columns are ~2.5× v7's — artifact age,
  not a crowding change.*
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

- Datable days: **7 of 7**, all present and non-partial on the observation
  side — raw rows per day: 128,792 / 204,781 / 205,082 / 205,847 / 205,163 /
  137,896 / 107,678 (weekend taper on Oct 10–11). 320,857 undated rows
  excluded (pre-date-column era), the same rule as v2–v7.

## 6. Continuity against the registered Oct-26 bands (not a scored window)

- The pre-registration registers continuity bands anchored on v7 — ghost
  1-in-200 to 1-in-330, all-day early 21.0–24.5%, AM 25–32% — as predictions
  for the weeks **after** the Oct-26 schedule change. This window is
  pre-change (the outgoing feed runs through 2026-10-25), so it is the
  continuity baseline the scored weeks will be read against.
- All three figures land where the registration expects a pre-change week:
  early share **22.6%** (inside 21.0–24.5%), AM **28.7%** (inside 25–32%),
  ghost **0.49%** (1 in 204, inside 1-in-200 to 1-in-330).
- The useful fact for the first scored week: the earliness basis is continuous
  at ~22.6% / 28.7%, so a post-change shift of more than ~1 pp will be signal
  against a stable baseline, not noise.

## What changes in v9

- Whether the ghost denominator recovers (it does not — v9 is worse: 4 of 7
  days have no ghost rows at all), so the backfill continues to carry the
  "rate not quotable" banner until the repair.
- Oct 12 runs **holiday** service (Thanksgiving Monday,
  `service_ids_on("2026-10-12")` resolves to a Holiday-1 block), so its
  volume and ghost rows are holiday-shaped, not weekday-shaped.

## Footer

- **Frozen:** 2026-10-26 (backfilled from the v10 cut). This snapshot is
  immutable; it will never be edited.
- Supersession: superseded by [v9](findings-v9-oct12-18.md); [v7](findings-v7-sept28-oct4.md)
  was superseded by this snapshot.
- **Correction:** the reliability denominator was repaired 2026-10-26 —
  [the erratum](erratum-2026-10-26-reliability-denominator.md) supersedes
  §0.2's prohibition on this page.
