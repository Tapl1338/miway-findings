# Feed-era comparison — 2017 wayback vintage vs 2026 live feed

- **Frozen:** 2026-09-04. This snapshot is immutable; it will never be edited.
  Superseded by: (none yet)
- **Question:** did the MiWay network shrink between the February 2017 feed
  ([wayback vintage](the GTFS archive manifest (private repo; SHAs cited inline)),
  `8ccdd201dcd9b44e`) and the live 2026 feed — or just re-shape?
- **Pinned dates (picker-proof):** both feeds filtered through the app's own
  weekday block, pinned to **2017-03-08** (`17FE27` weekday block, school
  session) and **2026-10-06** (`26SE07` weekday block, school session, first
  full post-Sept-7 month). School-session vs school-session controls for
  seasonality. Pin dates are recorded so any re-run is byte-comparable.
- **Method:** a pinned-date feed-comparison script (vintage analysis; see Reproducing). Route alignment by `route_short_name`; trip-hours =
  first-to-last departure per trip (a proxy that folds in layover — never a
  claim of true vehicle-hours). Stop-level and geographic analysis used the
  same pinned service sets.
- **Caveat that motivated the pinning:** an un-pinned "most common date"
  picker picked 2026-10-12-adjacent service and over-stated 2026 stop-visits
  by ~50%. All numbers below are pinned-date numbers.

## Network shape

| Metric | 2017 (pinned) | 2026 (pinned) | Δ |
|---|---|---|---|
| Routes with weekday service | 82 | 67 | −18% |
| Weekday trips | 5,421 | 4,900 | **−9.6%** |
| Revenue trip-hours (common routes) | 3,662 | 3,803 | **+3.8%** |
| Stops served | 3,436 | 3,130 | −8.9% |
| Culled routes | — | 22 | incl. 19 (Hurontario), 76, 34, 185 (Dixie Express) |
| Added routes | — | 7 | 2, 17, 18, 31, 74, 126, 135 |

The trip-count drop is real but not the story: vehicle-hours are essentially
flat. The network runs the same hours in fewer, longer, less-frequent trips
— the signature of a deliberate redesign (consolidation, frequency-over-
coverage), not of service cuts.

## Who lost access (the equity question)

450 of 3,436 stops (13.1%) appear in no 2026 weekday trip **by stop_id** —
but the stop inventory was rebuilt between eras, so id-matching overstates
loss. Matching geographically (straight-line walk to the nearest 2026 stop):

| Walk to nearest surviving stop | Lost stops |
|---|---|
| < 150 m (same corner, re-id'd) | 324 (72%) |
| < 300 m (5-minute walk) | 423 (94%) |
| ≥ 600 m (a real walk) | 4 |
| ≥ 800 m (access effectively gone) | **2** |

**True walk-access loss: 27 locations (≥300 m) = 6.0% of the 2017 stop
network.** Effective loss: 2 locations, both on **Dixie Rd at Balmoral
Dr / Clark Blvd** — the 2017 route 185 "Dixie Express" corridor. Context:
185 was a peak-only express (76 weekday trips, concentrated 05:00–09:00 and
14:00–19:00, 1.2% of 2017 trip-hours), and the nearest 2026 service today is
route 51 on Steeles, ~1.7 km away — so this is a genuine, nameable gap,
though one that a peak-express cancellation explains better than a systemic
retreat.

## Where the frequency went

Among stops served in **both** eras, weekday stop-visits fell 14.5%
(232,333 → 198,648; median 61 → 52/day) — the consolidated network serves
surviving stops less often, not more (the earlier +28% figure came from the
un-pinned holiday-adjacent 2026 date and is retracted). Concentration is
unchanged: the top decile of stops carried 9.5% of visits in both years —
the redesign did **not** pile service onto trunk corridors.

Measured boardings cannot adjudicate 2017 ridership: the collector measures
57 current routes over 2 days, and culled routes are never re-measured —
their ridership is honestly **unmeasurable** from present data.

## Verdict

Modest contraction (−10% trips), flat hours, 6% of stop locations farther
than a 5-minute walk from any stop — a frequency-for-coverage redesign with
one specific casualty (Dixie/Balmoral) rather than a broad withdrawal. The
ridership denominator remains open until the measured baseline matures.

## Reproducing

```
cd backend
python scripts/compare_feed_eras.py \
  --old <2017-feed-dir> --pinned-old 20170308 \
  --pinned-new 20261006 --csv culled_stops.csv
```

The 2017 feed is the Wayback Machine vintage of 2017-02-28 (SHA-256 on
file in the project archive manifest); the 2026 side is the live vendor
feed. All tables above are the complete script output for the pinned
dates.
