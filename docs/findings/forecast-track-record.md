# Forecasting track record — every pre-registered prediction, scored

> This project makes falsifiable predictions **before** the data exists,
> freezes them with SHA-256 manifests and GitHub timestamps, then lets a
> mechanical scorecard grade them — misses published alongside hits, always.
> This page is the running ledger. It grows one row-set per weekly cycle.
>
> **Ledger rule:** every registered band eventually gets a verdict row. A
> prediction that cannot be scored honestly is marked UNMEASURABLE with the
> artifact that proves why — never silently dropped.

## The rules (fixed in advance, never amended)

1. Predictions are committed publicly **before** the window's data exists
   (GitHub commit timestamps witness the ordering).
2. Bands are numeric; "direction" alone is never scored as a hit.
3. Scoring is mechanical (`sept7_scorecard.py` lineage) against the frozen
   evidence cut — never live CSVs, never memory, never judgment calls on
   borderline cases.
4. Verdict vocabulary: **PASS** / **FAIL-LOW** / **FAIL-HIGH** /
   **UNMEASURABLE** (with citation). No "close enough."
5. Refutations are published as-is. The ledger's authority comes from
   counting its own misses.

---

## Forecast 1 — September 7 changeover (the service-change test)

**Registered:** 2026-09-05 (before the change) · [pre-registration](../pre-registration-sept7.md) ·
**Scored FINAL 2026-09-22** from the frozen receipt (11 post-change weekdays, ≥10 rule met; Sept 7 was Labour Day and correctly excluded): `sept7-scorecard-verdict-20260922.md` (private-repo receipt, published values below).

| Band | Prediction | Verdict (FINAL) |
|---|---|---|
| Early departures, all day | 29.0–33.0% | **FAIL — 23.0%** (below band, improvement direction; FQ-10 basis note in receipt) |
| AM-peak early share | 35.0–39.0% | **FAIL — 28.3%** (below band, improvement direction) |
| Route 2 midnight occupancy | 40.0–44.0% | **FAIL — 36.7%** (below band; ±15-pt daily-spread fragility note applies) |
| Route 109 PM-rush occupancy | 38.0–42.0% | **FAIL — 45.8%** (above band) |
| Ghost rate | 2.5–3.5% | **UNMEASURABLE** — detector vintage replaced mid-window; no like-for-like denominator ([vintage audit](../ghost-ledger-vintage-audit.md)) |
| Network saved_pax_minutes | 9,500–10,000 | **UNMEASURABLE-AS-REGISTERED** — basis superseded; paired exhibit 10,179.6 (26AU03) → 19,368.0 (26SE07), OPTIMAL both sides |
| Ward 9 optimization delta | +1.5 to +3.5 | **FAIL-LOW** — −0.13 → −0.01; the changeover erased the ward's optimization headroom |

**FINAL tally: 0 PASS · 4 FAIL · 1 UNMEASURABLE · 1 UNMEASURABLE-AS-REGISTERED · 1 FAIL-LOW** (7 registered bands). The pre-registration predicted stability; the changeover delivered change. Every miss published with its cause — two of the four FAILs ran in the *improvement* direction, which is itself the finding: the service improved more than the model dared predict.

*Correction note (2026-09-18): this section originally published the preliminary verdicts under a FINAL header dated 2026-09-22 — a future date — which violated this ledger's own rule that only frozen receipts produce verdicts. Relabeled PRELIMINARY pending the actual receipt; the FINAL row above now replaces those values.*

## Forecast 2 — Week of Sept 14–20 (stability test I)

**Registered:** 2026-09-16 (before the window closed) · [pre-registration](../pre-registration-sept14-20.md) ·
**Scored 2026-09-22** from the v5 frozen cut (`findings-v5-sept14-20.md`, SHA manifest in the freeze record).

| Band | Prediction | Verdict |
|---|---|---|
| Ghost rate | 0.30–0.60% | **PASS** — 0.37% (109 of 29,605) |
| Early share, all day | 21.0–25.0% | **PASS** — 21.2% (n = 1,196,073) |
| Early share, AM peak | 25.0–29.0% | **PASS** — 26.0% (n = 127,887) |
| Top-5 ghost routes | ≥2 of {11, 66, 42, 103} | **FAIL** — only 11 repeated (61, 28, 110, 5 rounded out the top 5) |
| Route 2 late-night mean load | 46–52% | **FAIL-LOW** — 42% |
| Route 2 SRO+ share | 19–24% | **FAIL-LOW** — 17.8% |
| Route 109 PM mean / SRO+ | 41–47% / 16–22% | **PASS / FAIL-LOW** — 42% / 15.8% (0.2 pt) |

**Score: 4 PASS · 3 FAIL-LOW · 1 FAIL.** All crowding misses ran in the
less-crowded direction, matching the Sept-7 FINAL's miss direction. The
route-stability prior was falsified and stays retired (see the Sept 21–27
registration's process commitment 5).

## Forecast 3 — Week of Sept 21–27 (stability test II)

**Registered:** 2026-09-16 — two days before the *previous* window closed,
the earliest registration yet · [pre-registration](../pre-registration-sept21-27.md) ·
**Scored:** (pending — v6 freeze)

| Band | Prediction | Verdict |
|---|---|---|
| Ghost rate | 0.25–0.60% | pending |
| Early share, all day | 20.0–25.5% | pending |
| Early share, AM peak | 24.0–29.5% | pending |
| Route 2 late-night mean load | 44–53% | pending |
| Route 2 SRO+ share | 17–25% | pending |
| Route 109 PM mean / SRO+ | 40–48% / 15–23% | pending |

6 bands registered, predicted from the frozen v4 basis across two weeks
(basis caveat stated in the registration). New falsification threshold: if
all-day early share reaches v3's 26.3%, the post-change improvement has
fully reverted within 3 weeks — a different civic story, published as such.

---

## Running tally (updated at each freeze)

| Forecast | Bands | PASS | FAIL | UNMEAS | Scored |
|---|---|---|---|---|---|
| Sept 7 changeover | 7 | 0 | 4 (+1 FAIL-LOW) | 2 | yes (FINAL 2026-09-22) |
| Sept 14–20 | 8 verdicts / 7 bands | 4 | 4 | 0 | yes (v5 freeze) |
| Sept 21–27 | 6 | — | — | — | pending (v6 freeze) |
| Sept 28–Oct 4 | 6 | — | — | — | pending (v7 freeze) |
| **Total** | **25 bands** | **4** | **9** | **2** | 15 of 25 scored |

## Forecast 4 — Week of Sept 28–Oct 4 (stability test III)

**Registered:** 2026-09-22 · [pre-registration](../pre-registration-sept28-oct4.md) ·
**Scored:** (pending — v7 freeze)

| Band | Prediction | Verdict |
|---|---|---|
| Ghost rate | 0.30–0.50% | pending |
| Early share, all day | 19.0–22.5% | pending |
| Early share, AM peak | 24.0–27.5% | pending |
| Route 2 late-night mean / SRO+ | 38–48% / 14.5–21.5% | pending |
| Route 109 PM mean / SRO+ | 39–46% / 13.0–19.5% | pending |
| Drift test (all-day early ≤ v5 + 1 pt) | ≤ 22.2% | pending |

6 bands. First registration written after a FINAL scorecard existed: bands on
the two-week range, route-stability prior permanently retired, ghost band
pre-declared UNMEASURABLE if the detector vintage changes mid-window.

---

## Why the misses stay

A forecaster who only publishes hits is a marketing department. The
Sept-7 scorecard refuted 3 of its own 5 bands — including one *in the
improvement direction* (the service got better than predicted) — and that
refutation is more informative than the pass: it bounds the model, dates
the reversion risk, and demonstrates that the scoring cannot be talked out
of an honest verdict. When this ledger is long, its value will be the
misses, the UNMEASURABLEs, and what got learned from each.
