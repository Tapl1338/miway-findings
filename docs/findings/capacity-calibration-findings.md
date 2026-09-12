# Capacity assumption — empirical findings from the Aug 2026 ride-alongs

> **Version:** 1 (2026-08-23; analysis of ground truth collected Aug 18–21) · **Method:** implied capacity per check-in, `counted_pax ÷ (reported_pct/100)`, over 277 ride-along check-ins (188 plausible) · **Provenance:** full source is the private repo's `docs/capacity-calibration-findings.md`; this copy is verbatim in every measurement, with internal task references removed.

**Date:** 2026-08-23 (analysis of ground truth collected Aug 18–21)
**Question:** Is the reconstruction capacity assumption (65 pax standard /
110 pax articulated) fair?

**Answer:** Close but measurably high — and, more importantly, **no
fleet-level constant can be fair**, because two buses of the *same type*
(60-ft articulated) demonstrably respond differently.

## Method

Each ride-along check-in pairs a manual count (`counted_pax`) with the
displayed bucket (`reported_pct`). If the sensor divides true load by some
configured capacity C, then every check-in implies:

```
implied_C = counted_pax / (reported_pct / 100)
```

188 of 277 check-ins produced plausible implied values (30 ≤ implied ≤ 160;
the rest are floor/hysteresis artifacts — see caveats).

## Results

**Pooled:** median **55**, IQR 47–70, range 30–145.

**Per-vehicle medians** (n ≥ 5):

| Vehicle | Median implied C | n |
|---|---|---|
| 2240 | 45 | 21 |
| 4455 | 48 | 15 |
| 2101 | 52 | 31 |
| 2302 | 55 | 37 |
| 4318 | 55 | 13 |
| 2657 | 58 | 8 |
| 3289 ⚠️ artic | 59 *(lag-contaminated — see below)* | 20 |
| 3234 | 70 | 21 |
| 2694 ⚠️ artic | 92 | 22 |

Standard buses cluster ~45–70 (assumed: 65 → **~15% high**).
Articulated evidence spans **~92 vs unusable** (assumed: 110).

## The two-artic contrast (key finding)

Both vehicles were verified in the field as 60-ft artics (`vehicle_note`):
2694 = printed fleet 1794, Route 2; 3289 = printed fleet 2289, Route 42.

| Displayed bucket | 2694 counted-pax span | 3289 counted-pax span |
|---|---|---|
| "20%" | 13–29 | 11–23 |
| "40%" | 23–41 | **3–25** ⚠️ overlaps lower bucket |
| "60%" | 36–45 | — |

2694 tracks load tolerably. 3289 read "40% full" while the counted load fell
to **3 passengers** — its displayed value is nearly decoupled from load
(severe lag/hysteresis), which poisons any naive statistic computed over its
rows. **Descent readings contaminate medians; only ascent flip-transitions
are trustworthy.**

## Consequences

1. Absolute boarding estimates scale linearly with the constant → current
   lower bounds are inflated ~15% where standard buses dominate.
2. Relative rankings mostly survive, except routes with very different
   articulated-bus mixes.
3. Same-type vehicles behaving differently upgrades the APC audit ask:
   *MiWay should publish each vehicle's configured APC capacity and validate
   per vehicle* — identical buses demonstrably don't behave identically.

## Caveats

- Bucketed display means implied C within a band is bounded below by
  C_sensor; medians sit slightly above the configured value even when clean.
- 27 filtered rows include genuine floor-stuck artifacts AND possibly real
  low-capacity readings — treated as noise either way.
- Vehicle sample: 9 of ~500 fleet buses, routes 2/3/10/22/23/38/42/43/45/57/66/109,
  Aug 18–21 (weekday service only).

Reproducible via: `counted_pax ÷ (reported_pct/100)` over the raw
check-in log (`ground_truth.csv`); the method is documented above.
