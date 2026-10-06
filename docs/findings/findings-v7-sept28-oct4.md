# Findings snapshot v7 — fourth post-change week (Sept 28 – Oct 4)

> **FROZEN 2026-10-06.** This snapshot is immutable; corrections happen in
> v8, never here. Every number below was filled from the SHA-256 evidence
> freeze (6 artifacts, `evidence-freeze-v7/` in the private repo; manifest
> with per-file SHA-256s on file) via the pinned pipeline
> `derive_findings.py --start 2026-09-28 --end 2026-10-04 --source freeze`.
> **No bands were pre-registered for this window** — the Oct-26 template's
> bands are written at the Oct-12 freeze — so this is a week-over-week
> observational snapshot on the v4/v6 pattern, not a scored one.
>
> **Window caveats (declared at freeze, before publication):** all 7 days
> are datable and present. Oct 1–2 were backfilled after battery skips left
> the ghost ledger unwritten for those days (last write Sept 30); the
> freeze was taken only after a final analysis refresh completed with all
> 7 days synced. Three of the frozen artifacts are byte-identical
> carry-forwards from earlier freezes — written so the freeze is
> self-contained, not independent new measurements. The crowding figures
> below are a collection-wide aggregate with no date column (same caveat as
> every prior snapshot).

---

## 1. Reliability (fourth post-change week)

- Ghost trips: **89 of 22,492 verifiable trips never ran (0.396%, "1 in
  253")** — vs v4 0.39% (1/255), v5 0.37% (1/272), v6 0.43% (1/235). The
  post-changeover ghost regime held for a fourth week, still far better
  than the pre-change 1-in-118.
- Worst routes this week: **13 (10), 90 (8), 31 (7), 26 (6), 110 (5)**.
- Early departures ≥2 min (**FQ-10 basis, forecast-cap era** — never
  comparable to pre-change snapshots): **22.8%** (n = 756,644, canonical
  dedup); mean lateness +0.21 min. Series: 22.5% (v4) → 21.2% (v5) →
  22.1% (v6) → **22.8% (v7)** — same basis throughout; the post-change
  improvement holds at the v4–v5 level for a fourth week.
- AM-peak early share (07:00–09:00): **28.8%** (n = 77,336) — up from v5's
  26.0%. The AM series is the one that moved this week, worth watching
  against the Oct-26 schedule change.

## 2. Night crowding (raw APC, uncorrected — same basis discipline as v4/v5/v6)

- *occupancy_stats is a collection-wide aggregate — these figures cover the
  whole collection period as of the freeze point, not the window alone.
  Week-over-week moves here are mostly artifact growth, not behavior change.*
- Route 109 PM-rush: mean **42%** full, worst decile ≥ **100%**, SRO+
  **17.2%** (n = 208,993) — v6: 42% / 16.9%. Flat.
- Route 2 late-night: mean **40%** full, worst decile ≥ **140%**, SRO+
  **15.6%** (n = 120,731) — v6: 41% / 17.2%. Still the midnight-safety
  headline.
- Route 5 PM-rush: mean **35%** full, worst decile ≥ **100%**, SRO+ **9.2%**
  (n = 138,125).
- Routes averaging ≥33% full after 7 pm: **7** (2, 126, 61, 66, 49, 110,
  109) — v6: 7. The evening-service ask stands on the same evidence.

## 3. Collection health (this window)

- The cleanest week since the change: **7 of 7 days datable and present** —
  no coverage gaps, no mid-window copies. The battery-skip backfill and the
  final refresh both closed before the freeze, and every correction is
  stamped in the manifest.
- Week-over-week, on identical pinned bases, nothing regressed: the
  reliability gains hold and earliness sits inside the v4–v5 band for a
  fourth week.

## 4. APC field audit

- Hand-counted check-ins: **399** across **14** routes (frozen methodology
  reference, not a weekly metric).

## Footer

- **Frozen:** 2026-10-06. This snapshot is immutable; it will never be edited.
- Supersession: this is the current snapshot; [v6](findings-v6-sept21-27.md)
  is superseded.
