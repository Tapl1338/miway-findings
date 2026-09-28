# Findings snapshot v6 — third post-change week (Sept 21–27)

> **FROZEN 2026-09-28.** This snapshot is immutable; corrections happen in
> v7, never here. Every number below was filled from the SHA-256 evidence
> freeze (6 artifacts, `evidence-freeze-v6/` in the private repo; manifest
> with per-file SHA-256s on file) via the pinned pipeline
> `derive_findings.py --start 2026-09-21 --end 2026-09-27 --source freeze`.
> **No bands were pre-registered for this window** — the only
> pre-registrations on file are the Sept-7 scorecard and the Oct-26
> template — so this is a week-over-week observational snapshot on the v4
> pattern, not a scored one on the v5 pattern.
>
> **Window caveats (declared at freeze, before publication):**
> 1. **Coverage gap.** The Sept 24–25 cloud-box outage (~23.5h: Sept 24
>    22:23 → Sept 25 21:47 EDT) makes Sept 24 PARTIAL and Sept 25 HEAVILY
>    PARTIAL (12,149 rows ≈ 6% of a weekday). The guardrail held: unobserved
>    trips are marked *uncovered* (1,220 + 4,833) and excluded from the
>    verifiable denominator — they can never count as ghosts.
> 2. **Sept-27 mid-window copy.** The frozen cut captures Sept 27 at 22:44,
>    mid-evening-window, because the large-file sync channel stalled there
>    (collection itself ran to plan — all six Sept-27 windows completed
>    cloud-side). Raw Sept-27 rows (316,463) collapse to 102,179 unique
>    departures; **every headline figure below is on the canonical dedup
>    (freshest horizon per departure), so repeats never touch it.** Raw
>    row counts are a volume proxy only, and the raw Sept-27 count is not
>    quotable as one.

---

## 1. Reliability (third post-change week)

- Ghost trips: **116 of 27,217 verifiable trips never ran (0.43%, "1 in
  235")** — vs v4 0.39% (1/255) and v5 0.37% (1/272). The post-changeover
  ghost regime held for a third week; the outage removed trips from the
  verifiable denominator correctly (uncovered, not ghosts — only 2 of the
  week's 116 ghosts fell on the outage days).
- Worst routes: **61 (12), 110 (11), 36 (11), 22 (9), 11 (9)**. Route 61
  tops the list again (v5: 23) — the recurring offender across windows.
- Early departures ≥2 min: **22.1%** (n = 970,610, canonical dedup); mean
  lateness +0.30 min. Series: 22.5% (v4) → 21.2% (v5) → 22.1% (v6) — the
  post-change improvement holds for a third week. Same basis throughout.
- AM-peak early share: **26.3%** (n = 116,602). Stable (v4 26.4%, v5 26.0%).

## 2. Night crowding (raw APC, uncorrected — same basis discipline as v4/v5)

- *occupancy_stats is a collection-wide aggregate — these figures cover the
  whole collection period as of the freeze point, not the window alone.
  Week-over-week moves here are mostly artifact growth, not behavior change.*
- Route 109 PM-rush: mean **42%** full, SRO+ **16.9%** (n = 177,730) —
  v5: 42% / 15.8%. Flat.
- Route 2 late-night: mean **41%** full, SRO+ **17.2%** (n = 106,331) —
  v5: 42% / 17.8%. Flat.
- Routes averaging ≥33% full after 7 pm: **7** (2, 126, 61, 66, 49, 110,
  109) — v5: 8. The evening-service ask stands on the same evidence.

## 3. Collection health (this window)

- Weakest instrumentation week on record: 23.5h cloud-box outage
  (Sept 24–25) + a stalled large-file sync channel that froze the local
  copy mid-window on Sept 27. Complete days: **5/7 complete + 1 partial
  (outage) + 1 mid-window copy (cloud-side complete)** — every caveat
  stamped pre-publication in the freeze manifest.
- Week-over-week, on identical pinned bases, nothing regressed: the
  reliability and earliness gains survived the outage week intact.

## 4. Errata / corrections

One, against ourselves: the freeze-day hypothesis that Sept 27 showed a
"collector dedup failure" was **falsified** the same day by the coverage
ledger — multi-poll repeats within a window are the collector's designed
state (dedup runs at window close), and the anomaly was a stalled sync
channel, not an instrument defect. The manifest carries the correction; the
analysis rule it motivates (dedup before per-day analysis of a mid-window
cut) is unchanged.

## Footer

- **Frozen:** 2026-09-28. This snapshot is immutable; it will never be edited.
- Supersession: this is the current snapshot; [v5](findings-v5-sept14-20.md)
  is superseded.
