# Ground-truth ride-along insights

Source: `ground_truth.csv` (399 check-ins). Regenerate via `python scripts/ground_truth_insights.py`. Companion to `apc_bias_by_vehicle.md`, which answers *which buses*; this report answers *how bad, where in the range, and how long the lag lasts*.

## 1. Bucket-threshold brackets

39 observed bucket flips. Each brackets its threshold:

| Vehicle | From → To | Threshold lies between (pax) |
|---|---|---|

| 3289 | 20% → 40% | 23 – 25+ |
| 2657 | 40% → 20% | 6 – 7 |
| 2302 | 20% → 40% | 12 – 20+ |
| 2302 | 40% → 20% | 16 – 21 |
| 2302 | 20% → 40% | 14 – 15+ |
| 2302 | 40% → 20% | 14 – 14 |
| 2101 | 40% → 20% | 19 – 20 |
| 2101 | 20% → 40% | 19 – 20+ |
| 2101 | 40% → 20% | 14 – 19 |
| 4318 | 40% → 60% | 28 – 34+ |
| 4318 | 60% → 80% | 43 – 45+ |
| 4318 | 80% → 60% | 33 – 39 |
| 4318 | 60% → 40% | 13 – 21 |
| 4318 | 40% → 20% | 6 – 11 |
| 4420 | 20% → 40% | 6 – 11+ |
| 2240 | 20% → 40% | 16 – 17+ |
| 2240 | 40% → 20% | 10 – 15 |
| 2240 | 20% → 40% | 14 – 15+ |
| 2240 | 40% → 20% | 11 – 11 |
| 4455 | 20% → 40% | 16 – 16+ |
| 4455 | 40% → 20% | 9 – 11 |
| 2694 | 20% → 40% | 29 – 37+ |
| 2694 | 40% → 60% | 41 – 45+ |
| 2694 | 60% → 40% | 36 – 37 |
| 4444 | 40% → 20% | 13 – 14 |
| 2459 | 20% → 40% | 35 – 35+ |
| 2459 | 40% → 20% | 16 – 19 |
| 4341 | 20% → 40% | 11 – 17+ |
| 4341 | 40% → 20% | 17 – 20 |
| 4341 | 20% → 40% | 19 – 20+ |
| 4341 | 40% → 20% | 12 – 12 |
| 4327 | 20% → 40% | 14 – 18+ |
| 4327 | 40% → 60% | 18 – 21+ |
| 4327 | 60% → 80% | 22 – 36+ |
| 4327 | 80% → 60% | 27 – 34 |
| 2116 | 20% → 40% | 18 – 18+ |
| 2116 | 40% → 20% | 0 – 13 |
| 3232 | 20% → 40% | 18 – 24+ |
| 3232 | 40% → 20% | 13 – 16 |

`a – b+` = threshold is above a and at most b. For down-flips (`a – b`, no plus) the threshold lies between b and a.

Across 15 vehicles with brackets, 57 of 105 cross-vehicle bracket pairs overlap — overlap means two vehicles' thresholds are consistent with each other; non-overlap is direct evidence thresholds differ per vehicle.

## 2. Display lag after a real load change

- Stale-display events (≥4 pax moved, bucket unmoved): **44**
- Caught up before observations ended: 32 (never: 12)
- Median catch-up lag: **4.8 min** (p90 15.7 min)

## 3. Failure share by route

| Route | Check-ins | Floor-stuck | Flip-miss | Qualifying moves |
|---|---|---|---|---|
| 66 | 22 | 96% | 100% | 1 |
| 42 | 62 | 53% | 100% | 7 |
| 22 | 15 | 33% | 100% | 2 |
| 57 | 22 | 18% | 100% | 3 |
| 43 | 28 | 29% | 75% | 4 |
| 3 | 27 | 15% | 75% | 4 |
| 11 | 27 | 22% | 75% | 8 |
| 10 | 39 | 41% | 67% | 6 |
| 2 | 23 | 17% | 67% | 6 |
| 109 | 55 | 13% | 58% | 19 |
| 38 | 4 | 0% | 0% | 1 |
| 23 | 8 | 38% | - | 0 |

Caveats: brackets bound thresholds only where consecutive check-ins straddle a flip; lag is right-censored when observation ended before the display updated; small-n routes are directional.
