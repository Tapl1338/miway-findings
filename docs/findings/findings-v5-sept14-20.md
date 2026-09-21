# Findings snapshot v5 — second post-change week (Sept 14 – 20)

> **FROZEN 2026-09-21T21:20Z.** This snapshot is immutable; corrections
> happen in v6, never here. Every number below was filled from the SHA-256
> evidence freeze (6 artifacts, `docs/runs/evidence-freeze-v5/` in the
> private repo; manifest with per-file SHA-256s on file) via the pinned
> pipeline `derive_findings.py --start 2026-09-14 --end 2026-09-20
> --source freeze`. Ghost scoring: collection-window files Sept 14–21,
> ledger upserted.
> **Pre-registration:** [pre-registration-sept14-20.md](../pre-registration-sept14-20.md),
> committed 2026-09-16 before the window's data existed (GitHub timestamp
> witnesses it).
>
> **Window caveat (declared at freeze, before publication):** Sept 19 is a
> **partial day** — a collector gap (01:28–12:54 EDT) left morning service
> unobserved. Trips inside the gap are counted *uncovered*, never ghosts;
> the guardrail below records 6/7 complete days rather than pretending 7/7.

---

## 0. Pre-registered comparison — Sept 14–20 bands (THE core table)

| Metric | Pre-registered band | Observed (frozen cut) | Verdict |
|---|---|---|---|
| Ghost rate (verifiable trips) | 0.30–0.60% | 0.37% (109 of 29,605) | **PASS** |
| Early share, all day (≥2 min, FQ-10) | 21.0–25.0% | 21.2% (n = 1,196,073) | **PASS** (near low edge) |
| Early share, AM peak (07–09) | 25.0–29.0% | 26.0% (n = 127,887) | **PASS** |
| Top-5 ghost routes | ≥2 of {11, 66, 42, 103} | 61 (23), 11 (16), 28 (16), 110 (10), 5 (10) — only 11 repeats | **FAIL** |
| Route 2 late-night mean load | 46–52% | 42% (n = 87,517) | **FAIL-LOW** |
| Route 2 SRO+ share | 19–24% | 17.8% | **FAIL-LOW** |
| Route 109 PM mean / SRO+ | 41–47% / 16–22% | 42% / 15.8% (n = 141,438) | **PASS / FAIL-LOW (by 0.2 pt)** |

**Score: 4 PASS · 3 FAIL-LOW · 1 FAIL.** All four crowding misses point the
same way — *less crowded than predicted* — the same direction the Sept-7
scorecard's misses ran. Two honest reads: the fleet is running freer than
the changeover-era pattern suggested, and the bands were set from one week
(v4) plus a prior. The Route-2 measurement note (pre-drafted 2026-09-20,
before the verdict existed) applies in full:

> *Measurement note: the Route-2 late-night mean is a windowed average whose
> daily means swing widely — per-service-day means in the Sept 8–18 window
> ranged 27.4% to 57.6% (n≈2,000–3,100 polls/day). With daily spread of
> roughly ±15 points, a ±3-point band on the window mean is fragile: adding
> or dropping one sparse late-night day can move the verdict. The registered
> band is scored as-is (no post-hoc widening), and the falsification guard
> already prescribes the claim-softening response if the mean lands below
> 40%.*

**Falsification guards (checked at freeze):**
- Ghost rate 0.37%: between the guards (>1.0% schedule/data mismatch,
  <0.15% detector under-counting). **No guard fired.**
- Route 2 mean 42%: above the <40% softening trigger. The "night crowding
  is structural" claim is *qualified* (second week ran measurably freer)
  but not retracted.

### Collection-health guardrails (gate, not finding)

| Guardrail | Predicted | Observed | Gate |
|---|---|---|---|
| Measured departures (week) | 0.9–1.15M | 1,196,073 | above high edge (more data, not less) → proceed |
| Complete days | 7/7 by Tue Sept 22 | 6/7 (Sept 19 partial — collector gap) | caveat issued at freeze; proceeds |

---

## 1. Reliability (second post-change week)

- Ghost trips: **109 of 29,605 verifiable trips never ran (0.37%, "1 in
  272")** — vs v4 0.39% (1/255). The post-changeover ghost regime held for
  a second week. The Sept-19 collector gap removed 1,204 trips from the
  verifiable denominator correctly: they are *uncovered*, not ghosts.
- Early departures ≥2 min: **21.2%** (n = 1,196,073) — vs v4 22.5%. Down
  ~1.3 points; inside the registered band, at its low edge.
- AM-peak early share: **26.0%** (n = 127,887) — vs v4 26.4%. Stable.
- Top-5 ghost routes: **61 (23), 11 (16), 28 (16), 110 (10), 5 (10)** —
  v4 was 11 (15), 66 (12), 42 (11), 103 (10). Only route 11 repeats; the
  pre-registered "≥2 of {11, 66, 42, 103}" band **failed**. Honest
  reading: the worst-ghost roster is not stable week to week — it
  reshuffles. Week-over-week stability was a wrong prior, and the miss is
  now part of the record.

## 2. Night crowding (raw APC, uncorrected — same basis discipline as v4 §2)

- Route 2 late-night: mean **42%** full, **17.8%** SRO+ (n = 87,517) —
  v4: 49% / 21.7%. Both bands missed low.
- Route 109 PM-rush: mean **42%** full, **15.8%** SRO+ (n = 141,438) —
  v4: 44% / 19.4%. Mean inside band; SRO+ missed low by 0.2 pt.
- Both routes read *freer* than last week. Two candidate explanations,
  neither confirmed: the four-bucket APC display granularity (see the APC
  threshold-brackets finding) means SRO+ shares near thresholds move in
  steps rather than smoothly, and ~2–4 pt week-to-week ridership drift is
  within what that granularity can mask. The window mean of a metric with
  ±15-pt daily spread is fragile — the pre-registered note above was
  written precisely for this case.

## 3. The Sept-7 scorecard verdict (pointer — final lands Sept 22)

The mechanical scorecard for the **Sept-7 pre-registration** receives its
FINAL verdict on 2026-09-22, the day after this freeze. This section is
**intentionally a pointer, not a paraphrase**: the summary line will be
filled from the FINAL scorecard output only — the 2026-09-16 preliminary
is not citable — at v6's publication, per the pre-registration rules.
Receipt: `docs/runs/sept7-scorecard-verdict-20260922.md` (private repo;
public summary follows in the forecast ledger).

**Why this belongs in v5:** this week's own verdicts (Section 0) already
show the pattern — bands missed in the *improvement* direction (less
crowding, fewer early departures than registered) while the ghost regime
held. Whatever the Sept-7 final says, the prediction machinery is now
demonstrably willing to fail its own author in both directions. That is
the method working.

## 4. Errata / corrections

None. Every number was filled from the frozen cut in one pass; the Sept-19
partial-day caveat was declared at freeze, before publication, so no
post-hoc correction was needed.

## Footer

- **Frozen:** 2026-09-21T21:20Z. This snapshot is immutable; it will never be edited.
- **Comparison bases:** same metric definitions as v4 (ghost = verifiable-trip
  absence; early = ≥2 min before schedule; SRO+ = raw APC load ≥ seated
  capacity). No basis mixing. Derivation log: private-repo receipt with the
  freeze SHAs.
- **Next snapshot:** v6 (week of Sept 21–27), pre-registration due before
  the window's data lands.
