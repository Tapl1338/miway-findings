# Findings snapshot v5 — second post-change week (Sept 14 – 20)

> **DRAFT — STATUS banner per the findings procedure. Not immutable until
> frozen. Every number is a PLACEHOLDER (`TT`): fill from the frozen cut
> only, never from memory or chat. Do not publish until the pre-registered
> comparison table is complete and the guardrails have been checked.**
>
> **Version:** 5 — second post-change week · **Frozen:** (pending — fill at
> freeze time, then this file is never edited) · **Superseded by:** (none)
>
> **Source:** the SHA-256 evidence freeze (7 artifacts, Sept 14–20),
> windowed by the pinned pipeline
> `derive_findings.py --start 2026-09-14 --end 2026-09-20 --source freeze`.
> Ghost scoring over the window's collection-window files (ledger upserted);
> derivation log = private-repo receipt (SHAs on file).
> **Pre-registration:** [pre-registration-sept14-20.md](../pre-registration-sept14-20.md),
> committed 2026-09-16 before the window's data existed (GitHub timestamp
> witnesses it).

---

## 0. Pre-registered comparison — Sept 14–20 bands (THE core table)

Fill each row from the frozen cut. Verdict vocabulary: **PASS** (inside
band), **FAIL-LOW / FAIL-HIGH** (outside, direction named), **UNMEASURABLE**
(no like-for-like basis — cite the artifact that proves why).

| Metric | Pre-registered band | Observed (frozen cut) | Verdict |
|---|---|---|---|
| Ghost rate (verifiable trips) | 0.30–0.60% | TT% (TT of TT) | TT |
| Early share, all day (≥2 min, FQ-10) | 21.0–25.0% | TT% (n = TT) | TT |
| Early share, AM peak (07–09) | 25.0–29.0% | TT% (n = TT) | TT |
| Top-5 ghost routes | ≥2 of {11, 66, 42, 103} | TT | TT |
| Route 2 late-night mean load | 46–52% | TT% (n = TT) | TT |
| Route 2 SRO+ share | 19–24% | TT% | TT |
| Route 109 PM mean / SRO+ | 41–47% / 16–22% | TT% / TT% | TT |

**Falsification guards (from the registration — check before publishing):**
- Ghost rate >1.0% ⇒ schedule/data mismatch is back; investigate before any
  civic claim. <0.15% ⇒ detector under-counting (collection regression) —
  itself a finding.
- Route 2 mean <40% ⇒ the late-night pattern was changeover-specific; the
  "night crowding is structural" claim must be softened BEFORE it reaches
  civic materials.

### Collection-health guardrails (gate, not finding)

| Guardrail | Predicted | Observed | Gate |
|---|---|---|---|
| Measured departures (week) | 0.9–1.15M | TT | PASS → proceed / below 0.7M → DELAY FREEZE |
| Complete days | 7/7 by Tue Sept 22 | TT/7 | missing day ⇒ day-count caveat or delay |

---

## 1. Reliability (second post-change week)

> Fill the same section structure as v4 §1: headline ghost figure with the
> 1-in-N form, early-departure share with n, AM-peak concentration, and the
> week-over-week line vs v4 (and v3, since the stability question is
> explicitly "did v4 hold?"). Cite the frozen artifacts; note the ledger
> vintage (new-vintage basis, never mixed with pre-audit figures).

- Ghost trips: **TT of TT verifiable (TT%, "1 in TT")** — vs v4 0.39% (1/255)
- Early departures ≥2 min: **TT%** (n = TT) — vs v4 22.5%
- AM-peak early share: **TT%** (n = TT) — vs v4 26.4%
- Top-5 ghost routes: TT — v4 was 11 (15), 66 (12), 42 (11), 103 (10)

## 2. Night crowding (raw APC, uncorrected — same basis discipline as v4 §2)

- Route 2 late-night: mean **TT%** full, **TT%** SRO+ (n = TT) — v4: 49% / 21.7%
- Route 109 PM-rush: mean **TT%** full, **TT%** SRO+ (n = TT) — v4: 44% / 19.4%

## 3. The Sept-7 scorecard verdict (published this week — cross-reference, do not duplicate)

The mechanical scorecard for the **Sept-7 pre-registration** produced its
final verdict on 2026-09-22: **TT refuted, TT confirmed, one honest
UNMEASURABLE — published as-is** (scorecard receipt: `docs/runs/sept7-scorecard-verdict-20260922.md` (private-repo artifact, published after the Sept-22 FINAL run)
— private-repo receipt; summary line to be filled from the FINAL output,
never from the preliminary preview).

> Skeleton note: the expected shape (from the 2026-09-16 preliminary) is
> early-departure and AM-peak bands refuted in the IMPROVEMENT direction
> (service better than predicted), Route 2 midnight confirmed, ghost
> UNMEASURABLE per the vintage audit. Verify against the FINAL output
> before writing this paragraph — the preliminary is NOT citable. If the
> final verdicts differ, this section follows the final, not the
> expectation.

**Why this belongs in v5:** the Sept-7 stability bands failing low while
the Sept 14–20 persistence bands (Section 0) hold is the same story told
twice — v4 was not a lucky week, and the prediction machinery catches its
author being wrong in *both* directions. That is the method working.

## 4. Errata / corrections

> (Expected: none. If any number moved between draft and freeze, it goes
> here, not silently — same rule as v1's 1-in-32 note.)

## Footer (fill at freeze)

- **Frozen:** TT (UTC). This snapshot is immutable; it will never be edited.
- **Comparison bases:** same metric definitions as v4 (ghost = verifiable-trip
  absence; early = ≥2 min before schedule; SRO+ = raw APC load ≥ seated
  capacity). No basis mixing.
- **Next snapshot:** v6 (week of Sept 21–27), pre-registration due before
  the window's data lands.
