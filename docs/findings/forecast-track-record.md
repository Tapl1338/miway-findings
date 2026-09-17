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
**Scored:** 2026-09-22 · **Mode:** FINAL · [scorecard](../runs/sept7-scorecard-verdict-20260922.md)

| Band | Prediction | Verdict |
|---|---|---|
| Early departures, all day | 29.0–33.0% | **FAIL-LOW** (improvement direction — see basis note in scorecard) |
| AM-peak early share | 35.0–39.0% | **FAIL-LOW** (same) |
| Route 2 midnight occupancy | 40.0–44.0% | **PASS** |
| Route 109 PM-rush occupancy | 38.0–42.0% | **FAIL-HIGH** |
| Ghost rate | 2.5–3.5% | **UNMEASURABLE** — detector vintage replaced mid-window; no like-for-like denominator ([vintage audit](ghost-ledger-vintage-audit.md)) |

**Tally: 1 PASS · 3 FAIL · 1 UNMEASURABLE.**
The misses are the point: the improvement was *larger than predicted*, and
the model said so mechanically rather than taking credit.

*Status: verify each verdict against the FINAL scorecard output at
publication time; the 2026-09-16 preliminary expected this shape but is not
citable.*

## Forecast 2 — Week of Sept 14–20 (stability test I)

**Registered:** 2026-09-16 (before the window closed) · [pre-registration](../pre-registration-sept14-20.md) ·
**Scored:** (pending — v5 freeze)

| Band | Prediction | Verdict |
|---|---|---|
| Ghost rate | 0.30–0.60% | pending |
| Early share, all day | 21.0–25.0% | pending |
| Early share, AM peak | 25.0–29.0% | pending |
| Top-5 ghost routes | ≥2 of {11, 66, 42, 103} | pending |
| Route 2 late-night mean load | 46–52% | pending |
| Route 2 SRO+ share | 19–24% | pending |
| Route 109 PM mean / SRO+ | 41–47% / 16–22% | pending |

7 bands registered. Verdicts fill at the v5 freeze; falsification guards are
in the registration.

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
| Sept 7 changeover | 5 | 1 | 3 | 1 | yes (FINAL 2026-09-22) |
| Sept 14–20 | 7 | — | — | — | pending |
| Sept 21–27 | 6 | — | — | — | pending |
| **Total** | **18** | **1** | **3** | **1** | 5 scored |

## Why the misses stay

A forecaster who only publishes hits is a marketing department. The
Sept-7 scorecard refuted 3 of its own 5 bands — including one *in the
improvement direction* (the service got better than predicted) — and that
refutation is more informative than the pass: it bounds the model, dates
the reversion risk, and demonstrates that the scoring cannot be talked out
of an honest verdict. When this ledger is long, its value will be the
misses, the UNMEASURABLEs, and what got learned from each.
