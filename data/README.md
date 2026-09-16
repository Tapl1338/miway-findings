# Observed lateness — public sample

A 250,000-row uniform random sample of the project's observed-departure
dataset: **what MiWay buses actually did**, measured from the agency's own
real-time feed, 24/7, every 30 seconds.

- **Full dataset:** 3,601,272 unique dated recorded departures (as of 2026-09-16; still counting) — shipped in full as `lateness-actuals-full-dated.csv.gz`
- **This file:** `lateness-sample-250k.csv` — 250,000 rows, ~9.3 MB, uniform random draw (seed `20260911`) from the full set
- **Span:** Aug 23 – Sep 15, 2026 (all rows)
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
| `dep_time_min` | float | scheduled departure time, minutes since midnight (e.g. `510.0` = 08:30; values ≥ 1440 are post-midnight service-night departures, dated to the calendar day they occurred) |
| `lateness_minutes` | float | observed delay in minutes. **Negative = early.** `-3.0` means the bus left three minutes before its scheduled time — invisible to anyone following the timetable |
| `horizon_minutes` | float | how far ahead the feed's prediction was when captured. This sample contains **recorded actuals only** (`horizon ≤ 0`): the reading taken after the stop was passed — the observed fact, not a forecast. Forecasts are excluded because the vendor's predictions carry a systematic early bias (measured: future forecasts average ~4.8 min early; passed-stop actuals ~0.19 min) |
| `date` | string | observation date, `YYYY-MM-DD`, Toronto local time — **never empty in this sample** |

## Processing rules (pinned, reproducible)

1. One row per poll; a departure still in the feed is re-emitted each poll.
   The canonical reader deduplicates on
   `(route_short_name, stop_id, dep_time_min, date)`, keeping the
   **most-negative horizon** — the freshest reading, i.e. the recorded
   actual. This sample applies that exact rule before sampling.
2. Rows with `horizon_minutes > 0` (future forecasts) are excluded entirely.
3. **Dated rows only.** Captures from before 2026-08-23 predate the
   observation-`date` column (the collector's migration deliberately leaves
   their dates empty, and they carry no trip anchor to recover one). Those
   ~307,866 legacy rows are excluded here, exactly as they are by every
   internal per-date analysis (the FQ-10 rule). The first three weeks of
   August are therefore not represented in this sample; from Aug 23 onward
   coverage is continuous.
4. The sample is a uniform random draw (seed `20260911`) from the
   deduplicated **dated-actual** set — every recorded departure had an
   equal chance, so sample statistics estimate the full dataset's.

## Reproducibility

The seed pins the draw *given the input corpus*; the corpus grows daily, so
the input fingerprint below is part of the provenance chain. Regenerate
with the private repo's `backend/scripts/make_public_sample.py`
(--dry-run prints the same funnel without writing).

| provenance | value |
|---|---|
| built | 2026-09-16 |
| input `obs_lateness.csv` SHA-256 | `49ce007775ae8a474d2d144fa36799bc24e20d88240641f976c5195150064821` |
| input rows | 4,591,161 |
| → after canonical dedup | 4,252,796 |
| → after actuals filter (`horizon ≤ 0`) | 3,909,138 |
| → after dated filter (legacy undated dropped) | **3,601,272** |
| seed | `20260911` |
| output SHA-256 (sample) | `433875dc3cc709931f5213cb8b0449192fc80ebb666de0c833d1500e3f4e4613` |
| output SHA-256 (full corpus, gz) | `870c2e0ede5c5ad399dd076dfceabd9c30a2b75dae93bf47cbbddc076932608e` |
| empty dates / forecast rows in output | 0 / 0 (hard gate) |

Note: the gz output fingerprint is not byte-reproducible (gzip headers
carry a creation timestamp); the reproducibility anchors are the input
SHA-256, the pinned rules, and the funnel counts above — re-running the
pipeline against the same input must reproduce all three. The 250k
sample CSV is byte-reproducible given the same input (plain CSV, seed-pinned).

## Things you can compute from this

- **Early-departure rate:** share of rows with `lateness_minutes < -2` —
  the "early bus is a missed bus" finding. In this sample's window it is
  **~25%** (row basis); it ran nearer 30% earlier in the summer, so treat
  the rate as era-dependent, not constant.
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
- **Pre-Aug-23 captures are absent by design** (rule 3): the observation
  date did not exist for them, and rather than ship a partially-empty
  column, the sample starts where dating starts.
- The full dataset carries the same schema and rules; the sample exists
  because the corpus is the size it is. If you need the full set for
  replication, open an issue.

## Versioning & deposit

- **[ZENODO-METADATA.md](ZENODO-METADATA.md)** — the copy-paste upload kit
  (title, abstract, methods, keywords, checklist).
- **[VERSIONING.md](VERSIONING.md)** — the frozen-deposit policy: once the
  DOI mints, v1.0.0 is immutable; corrections and bigger re-cuts ship as
  new versions of the same record (concept DOI stays stable). The version
  table with every past DOI lives there.

## Citation

If you use this data, a link to this repository is the requested citation.
Findings built on it live in the [weekly snapshots](../README.md#what-the-data-shows),
each frozen with a SHA-256 evidence manifest in the private archive.
