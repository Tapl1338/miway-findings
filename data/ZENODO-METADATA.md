# Zenodo deposit metadata — copy-paste ready

> **This is now a record of what is published, not a pre-upload kit.**
> v1.0.0 (2026-09-17, DOI `10.5281/zenodo.22820449`) and v1.1.0
> (2026-10-18, DOI `10.5281/zenodo.23444830`) are live under concept DOI
> `10.5281/zenodo.22820448`; the next version is cut by
> `backend/scripts/publish_zenodo_version.py` in the private repo, which
> builds the payload, uploads it and writes the metadata — nothing here is
> pasted by hand any more. Fields below describe the newest published cut.

## 1. Basic fields

| Zenodo field | Value |
|---|---|
| **Resource type** | Dataset |
| **Title** | Observed bus departure lateness, MiWay (Mississauga, Canada), August–October 2026 |
| **Publication date** | 2026-10-18 (v1.1.0) |
| **Creators** | Lin, Ethan — role: Data collector, Data curator, Project leader |
| **Description** | Paste the **Abstract** below |
| **Keywords** | `public transit` `bus punctuality` `GTFS-RT` `real-time feed` `departure delay` `early departure` `Mississauga` `MiWay` `open data` |
| **License** | `MIT License` (the repo's license — same grant for the data) |
| **Funding** | none — independent, unfunded project |
| **Access** | Open |
| **DOI** | version DOI `10.5281/zenodo.23444830` (v1.1.0); concept DOI `10.5281/zenodo.22820448` for citations |

## 2. Abstract (paste into "Description")

Dataset of 250,000 observed bus departures (with the complete 8,031,942-row
corpus included as a companion file) recorded from the GTFS-RT
`TripUpdate` feed of MiWay, the municipal transit agency of Mississauga,
Ontario, Canada (population ~715,000). The platform polled the agency's
published real-time feed every 30 seconds, 24/7, from 2026-08-23 to
2026-10-17, and joined each scheduled departure to the timetable to record
what each bus actually did. Each row is one scheduled bus departure at one
stop with its observed deviation from schedule, in minutes
(negative = early). The sample is a uniform random draw (seed 20260911)
from the 8,031,942 deduplicated recorded actuals (predictions excluded — the
vendor's forecasts carry a measured ~4.8-minute early bias; only readings
taken after the stop was passed are included).

Notable properties: (1) the vendor's real-time feed systematically
*over-anticipates* earliness — network-wide, roughly a quarter of
departures in this window left more than two minutes early, a modality of
unreliability invisible to riders following the timetable and absent from
on-time-performance statistics that clamp early arrivals to "on time";
(2) early departures concentrate in the AM peak and at school-door stops;
(3) the sample is released with a full provenance chain — input/output
SHA-256 fingerprints, pinned dedup rules, and the sampling seed — so every
figure is regenerable. Future forecasts (`horizon_minutes > 0`) and
pre-2026-08-23 captures (which predate the observation-date column) are
excluded by pinned rules; see the README for the complete processing
rules and caveats. Departure delay is not rider wait time — headway-based
wait depends on differences between consecutive buses.

## 3. Files to upload

| file | what it is |
|---|---|
| `lateness-actuals-full-dated.csv.gz.part01..17` | the **complete** dated-actuals corpus — 8,031,942 rows, ~70 MB gzipped, shipped as 17 byte splits of ONE gzip stream (concatenate in order, then gunzip) |
| `lateness-sample-250k.csv` | seed-pinned uniform random sample (250,000 rows, ~9.4 MB) — the approachable, byte-reproducible verification file |
| `README.md` | the data dictionary + processing rules — upload as a file (cleaner than pasting into notes) |

## 4. Data dictionary (also in README; paste where Zenodo asks or leave in the uploaded README)

| column | type | meaning |
|---|---|---|
| `route_short_name` | string | GTFS route short name (e.g. `2`, `109`) |
| `stop_id` | string | GTFS stop ID, zero-padded as the feed writes it (`0042` ≠ `42`) |
| `dep_time_min` | float | scheduled departure, minutes since midnight (`510.0` = 08:30; ≥ 1440 = post-midnight service-night departure, dated to the calendar day it occurred) |
| `lateness_minutes` | float | observed deviation from schedule, minutes; **negative = early** |
| `horizon_minutes` | float | prediction lead time at capture; ≤ 0 in every row (recorded actual, reading taken after the stop was passed) |
| `date` | string | observation date `YYYY-MM-DD`, Toronto local time; never empty |

## 5. Method (paste into "Methods" — or leave in the uploaded README)

- **Source:** MiWay's public GTFS-RT `TripUpdate` feed (the same feed any
  rider app consumes) plus the matching GTFS static timetable. No
  proprietary data; no scraping of non-public systems.
- **Collection:** a collector polls the feed every 30 seconds, 24/7. Each
  poll captures predicted departures; a departure still in the feed is
  re-emitted each poll with an ever-more-negative prediction lead time.
- **Dedup:** one row per unique
  `(route_short_name, stop_id, dep_time_min, date)`, keeping the
  most-negative horizon — the last reading before the departure left the
  feed window, i.e. the recorded actual.
- **Actuals filter:** rows with `horizon_minutes > 0` (future forecasts)
  are excluded; the vendor's forecasts carry a measured systematic early
  bias (future forecasts mean ~4.8 min early vs ~0.19 min for passed-stop
  actuals).
- **Dated filter:** captures from before 2026-08-23 predate the
  observation-date column and are excluded (the collector's migration
  leaves their dates empty; they carry no trip anchor to recover one).
  Coverage is continuous from 2026-08-23.
- **Sampling:** uniform random draw without replacement, seed `20260911`
  (NumPy `default_rng`), from the 8,031,942-row dated-actual set sorted in
  corpus order. The full, unsampled corpus is included as
  `lateness-actuals-full-dated.csv.gz`; the sample exists as the
  byte-reproducible verification artifact. The input corpus SHA-256 is
  recorded with the deposit.
- **Post-midnight convention:** a departure with `dep_time_min ≥ 1440`
  belongs to the service night that began the previous calendar day; its
  `date` is the calendar day the departure physically occurred.

## 6. Related identifiers (fill at publish time)

| relation | identifier |
|---|---|
| `is supplement to` | `https://github.com/Tapl1338/miway-findings` (the findings showcase repo) |
| `is referenced by` | weekly findings snapshots (linked from the repo README) |
| `is variant form of` | *(optional)* the repo tag `demo-20260915` or the release that froze the dataset |

## 7. Cutting the next version (what replaced the checklist)

The upload is scripted (`backend/scripts/publish_zenodo_version.py`, see
`docs/uni/zenodo-cadence.md` in the private repo): build the corpus once,
draw the sample from that frozen file, upload the files, PUT the metadata
and publish. Two things this page cannot do for you, learned the hard way
on 2026-10-18:

1. **This concept is a legacy Zenodo deposition.** Descriptive metadata is
   written through `PUT /api/deposit/depositions/{id}` (fields nested under
   `metadata`, legacy names: `upload_type`, string `license`). The
   records-side `PUT /api/records/{id}/draft` answers **200 and drops every
   field** — a write is proven by reading it back, never by the status code.
2. **Re-cut the versioned copy of this page and `data/README.md`** with the
   new counts, window, fingerprint trio and version row (§ VERSIONING.md).
   A reader who downloads the deposit and diffs it against this repo should
   find the same SHA-256s.
