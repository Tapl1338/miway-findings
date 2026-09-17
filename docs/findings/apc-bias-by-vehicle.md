# APC display bias by vehicle

Source: `ground_truth.csv` — 399 check-ins across 20 vehicles; the table below tabulates the 332 complete observations (display reading + counted load both present) across 17 vehicles. Vehicles with incomplete readings are excluded (incl. 2263/4444, which sit above the <10 'directional only' line — observation losses, not directional-only). Re-derivable via `python scripts/apc_bias_by_vehicle.py`; raw check-ins carry observer counts against the on-board display bucket.

| Vehicle | Routes | Check-ins | Floor-stuck | Flip-miss | Down-flip wrong | Widest bucket span (pax) | Overlap buckets | Model | Garage |
|---|---|---|---|---|---|---|---|---|---|
| 4327 | 109 | 17 | 6% | 62% | 38% | ±6 | 1/4 | 2023 stan | CP |
| 4318 | 109 | 19 | 0% | 56% | 22% | ±11 | 2/4 | 2023 stan | CP |
| 2302 | 10 | 39 | 41% | 67% | 33% | ±6 | 1/2 | 2012 stan | CP |
| 3289 | 42 | 24 | 33% | 100% | 50% | ±11 | 1/2 | 2022 arti | CP |
| 3232 | 11 | 16 | 19% | 80% | 40% | ±9 | 1/2 | 2022 stan | CP |
| 2694 | 2 | 23 | 17% | 67% | 33% | ±10 | 2/3 | 2017 arti | CP |
| 2459 | 42 | 36 | 64% | 100% | 33% | ±11 | 1/2 | 2013 arti | CP |
| 2240 | 43 | 28 | 29% | 75% | 50% | ±7 | 1/2 | 2011 stan | CP |
| 4455 | 57 | 22 | 18% | 100% | 33% | ±6 | 1/2 | 2024 stan | CP |
| 2101 | 3 | 27 | 15% | 75% | 25% | ±7 | 1/2 | 2010 stan | CP |
| 2657 | 22 | 15 | 33% | 100% | 50% | ±5 | 1/2 | 2017 stan | M |
| 4341 | 11 | 11 | 27% | 67% | 67% | ±8 | 1/2 | 2023 stan | CP |
| 3234 | 66 | 22 | 96% | 100% | 0% | ±4 | 0/1 | 2022 stan | CP |
| 2116 | 109 | 19 | 32% | 50% | 0% | ±9 | 1/2 | 2010 stan | CP |
| 3282 | 42 | 2 | 100% | 0% | 0% | ±1 | 0/1 | 2022 arti | CP |
| 4444 | 23 | 8 | 38% | 0% | 0% | ±2 | 0/2 | 2024 stan | CP |
| 4420 | 38 | 4 | 0% | 0% | 0% | ±0 | 0/2 | 2024 stan | CP |

Fleet-wide: **44/61** qualifying load moves (72%) produced no bucket change.

Caveats: vendor bucket thresholds are unknown, so shares describe the *displayed* response to *observed* load moves, not sensor error in passengers. Vehicles with <10 check-ins are directional only.
