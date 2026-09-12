# School crowding is a trip-level phenomenon — the v2 re-analysis

> **Version:** 2 (2026-09-12; supersedes the v1 route-level snapshot in
> *method* only — v1's route numbers remain valid as the route-proxy view)
> · **Data:** vehicle occupancy feed (APC), snapshots 2026-08-17 →
> 2026-09-12 (207 collection files) · **Method:** each trip's school flag
> is derived from the GTFS timetable itself, not from a static route list
> · **Eras:** full corpus spans the Sept 7 schedule change; the school era
> is 2026-09-08 onward · **Bell calendar re-verified 2026-09-11** · Full
> receipt with CSVs: private repo
> `docs/runs/school-era-control-receipt-20260912.md` (SHA on file).

## What changed from v1

The unit of analysis moves from **route** to **trip**. V1 labeled whole
routes school-serving via a static route set, which credits off-wave trips
and mislabels mixed corridors. V2 derives each trip's flag from the
timetable itself:

| Level | Meaning |
|---|---|
| `at_door` | trip has a scheduled stop at a school's own transit stop inside the bell-time wave window |
| `walkshed` | trip serves any stop within 800 m straight-line of a school anchor in-window |
| `route_proxy` | trip not in the weekday timetable (weekend/holiday variants, feed drift); v1 route-level fallback |
| `none` | control group |

Vintage safety (the 2026-09-06 lesson — "an unfiltered GTFS join is not
service"): flags are built from the **union of all Weekday service_ids
across both schedule vintages**, since the corpus spans the changeover.
The route-level *false-service rule* is deliberately NOT applied at trip
level: a 306 full of one school's students is school crowding even if the
*service* belongs to another school.

**Delivery window** (the key sharpening): at-door observations are split
by whether they fall within **25 min before → 5 min after** a scheduled
school-stop departure. Buses fill on the approach and shed students at
the door — the whole-wave cut dilutes the packed approach with the
emptied continuation.

## Validation: the bell burst, measured

One school's bell schedule produces the strongest scheduled-extras
signature in the network's school calendar: three buses on one route
departing that school's own stop at **14:32, 14:34, and 14:41**, plus an
activity tail to 15:41. The school-era observations of exactly those
three bell trips, approach window only:

| Trip | n | mean % | p90 % | obs ≥ 60% |
|---|---|---|---|---|
| 30463254 (14:32 dep) | 234 | 41.5 | 80 | 20.5% |
| 30490698 (14:34 dep) | 226 | 31.0 | 60 | 11.5% |
| 30490699 (14:41 dep) | 231 | 38.3 | 80 | 20.8% |

The three bell trips run hot (mean 31–42%, p90 60–80%) against their
route's school-era PM wave mean of 34.2% — and far above the v1
whole-wave route number (2.5% crowded) that motivated this rework. The
lived observation ("right after the 2:20 bell the buses are all
massively full") reproduces from the feed.

## Route-level results (school era, delivery window, n ≥ 100)

PM approach, at-door, by crowded share: route 8 → **24.6%**, route 38 →
**14.5%**, 13 → 13.4%, 28 → 9.9%, 302 → 8.8%, 315 → 8.2%. AM: route 38's
approach cut runs 21.8% crowded (1,545 obs).

Whole-wave level split (full corpus, AM): at-door 30.3% mean / 6.8%
crowded, walkshed 30.0 / 6.9, route_proxy 28.7 / 5.6, none 29.3 / 6.5 —
the AM school effect stays hidden at wave level (the AM peak is
school-saturated overall, so the split can't isolate students there).
PM: at-door 28.1 / 4.1 vs route_proxy 30.2 / 7.0 — the route-level PM
"school effect" from v1 largely dissolves once trips are resolved: the
crowding lives in *specific bell trips*, not in school routes generally.
That is the v2 headline: **school crowding is a trip-level phenomenon,
and only trip-level analysis sees it.**

## Caveats

- School anchors come from GTFS stop names — 10 distinct schools resolve
  (the school calendar's walkshed tables cover 19; the rest have no named
  stop and live only in walkshed/proxy levels).
- `route_proxy` still carries weekend/holiday trips, which have no school
  waves; it exists so the split degrades gracefully, never to support a
  headline number.
- Occupancy percentages are raw APC sensor output (bucket-threshold
  artifacts documented in the [APC audit](apc-threshold-brackets.md)); the
  200% cap matches the standard aggregator.
- Small-n school extras (307, 315, 314) remain volatile.

## Next steps

1. Era split × school_level for the like-for-like control (the date
   column is now present in the row data).
2. Resolve the 87-audit pre-registered prediction — crush loads
   on the 07:51 route 38 trip — with this same delivery-window machinery
   on the AM side once enough school-era AM days accumulate.
3. Bell-alignment comparison: do MiWay's *bell-aligned* school trips (the
   Sept-7 notice list) deliver lower approach crowding than the ad hoc
   ones?
