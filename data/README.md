# Observed lateness — public sample

A 250,000-row uniform random sample of the project's observed-departure
dataset: **what MiWay buses actually did**, measured from the agency's own
real-time feed, 24/7, every 30 seconds.

- **Full dataset:** 3,228,763 unique recorded departures (and counting)
- **This file:** `lateness-sample-250k.csv` — 250,000 rows, ~9 MB
- **Span:** Aug 18 – Sep 11, 2026 (all sampled rows)
- **License:** MIT (see repo root)

## How it was collected

The platform polls MiWay's published GTFS-RT `trip_update` feed every 30
seconds around the clock and joins each predicted departure to the static
GTFS timetable. Each row is one scheduled bus departure at one stop, with
what the feed last said before it happened. No proprietary data, no
scraping of non-public systems — the same feeds any rider app sees.

## Columns

| column | type | meaning |
|---|---|---|
| `route_short_name` | string | GTFS route short name (e.g. `2`, `109`) |
| `stop_id` | string | GTFS stop ID, **zero-padded as the feed writes it** (`0042` ≠ `42`) |
| `dep_time_min` | float | scheduled departure time, minutes since midnight (e.g. `510.0` = 08:30) |
| `lateness_minutes` | float | observed delay in minutes. **Negative = early.** `-3.0` means the bus left three minutes before its scheduled time — invisible to anyone following the timetable |
| `horizon_minutes` | float | how far ahead the feed's prediction was when captured. This sample contains **recorded actuals only** (`horizon ≤ 0`): the reading taken after the stop was passed — the observed fact, not a forecast. Forecasts are excluded because the vendor's predictions carry a systematic early bias (measured: future forecasts average ~4.8 min early; passed-stop actuals ~0.19 min) |
| `date` | string | observation date, `YYYY-MM-DD`, Toronto local time |

## Processing rules (pinned, reproducible)

1. One row per poll; a departure still in the feed is re-emitted each poll.
   The canonical reader deduplicates on
   `(route_short_name, stop_id, dep_time_min, date)`, keeping the
   **most-negative horizon** — the freshest reading, i.e. the recorded
   actual. This sample applies that exact rule before sampling.
2. Rows with `horizon_minutes > 0` (future forecasts) are excluded entirely.
3. The sample is a uniform random draw (seed `20260911`) from the deduplicated
   set — every recorded departure had an equal chance, so sample statistics
   estimate the full dataset's.

## Things you can compute from this

- **Early-departure rate:** share of rows with `lateness_minutes < -2` —
  the "early bus is a missed bus" finding (network-wide it has held near 30%
  all summer).
- **Lateness by hour:** group `lateness_minutes` by
  `dep_time_min // 60` — the AM-peak early-departure concentration.
- **Per-route distributions:** the project's optimizer samples connection
  lateness from per-route distributions like these instead of assuming a
  parametric shape.

## Caveats (read before quoting)

- **This is departure delay, not arrival delay or wait time.** Headway-based
  rider wait depends on *differences* between consecutive buses, not
  absolute lateness.
- **Feed-side measurement.** If a bus never appears in the real-time feed at
  all ("ghost trip"), it generates no rows here — ghost measurement is a
  separate pipeline joining scheduled trips against feed presence.
- **Single agency, single region.** Patterns here describe MiWay's network;
  don't generalize the rates elsewhere.
- The full dataset carries the same schema and rules; the sample exists
  because the corpus is the size it is. If you need the full set for
  replication, open an issue.

## Citation

If you use this data, a link to this repository is the requested citation.
Findings built on it live in the [weekly snapshots](../README.md#what-the-data-shows),
each frozen with a SHA-256 evidence manifest in the private archive.
