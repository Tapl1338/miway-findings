# Zenodo deposit metadata — copy-paste ready

> Everything on this page is filled in and verified against the current
> sample (regenerated 2026-09-15; empty-date fix, see data/README.md rule 3).
> Only two fields need you at upload time: your **ORCID** and the
> **related identifier** once Zenodo assigns the concept DOI.

## 1. Basic fields

| Zenodo field | Value |
|---|---|
| **Resource type** | Dataset |
| **Title** | Observed bus departure lateness, MiWay (Mississauga, Canada), August–September 2026 |
| **Publication date** | (today's date at upload) |
| **Creators** | Lin, Ethan (ORCID: `FILL-IN`) — role: Data collector, Data curator, Project leader |
| **Description** | Paste the **Abstract** below |
| **Keywords** | `public transit` `bus punctuality` `GTFS-RT` `real-time feed` `departure delay` `early departure` `Mississauga` `MiWay` `open data` |
| **License** | `MIT License` (the repo's license — same grant for the data) |
| **Funding** | none — independent, unfunded project |
| **Access** | Open |
| **DOI** | leave as *Concept DOI* (minted on first publish) |

## 2. Abstract (paste into "Description")

Dataset of 250,000 observed bus departures recorded from the GTFS-RT
`TripUpdate` feed of MiWay, the municipal transit agency of Mississauga,
Ontario, Canada (population ~715,000). The platform polled the agency's
published real-time feed every 30 seconds, 24/7, from 2026-08-23 to
2026-09-15, and joined each scheduled departure to the timetable to record
what each bus actually did. Each row is one scheduled bus departure at one
stop with its observed deviation from schedule, in minutes
(negative = early). The sample is a uniform random draw (seed 20260911)
from 3,599,079 deduplicated recorded actuals (predictions excluded — the
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
| `lateness-sample-250k.csv` | the dataset (250,000 rows, ~9.3 MB) |
| `README.md` | the data dictionary + processing rules (paste as "Additional notes" or upload as a second file — upload as file is cleaner) |

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
  (NumPy `default_rng`), from the 3,599,079-row dated-actual set sorted in
  corpus order. The seed pins the draw given the input corpus; the input
  corpus SHA-256 is recorded with the deposit.
- **Post-midnight convention:** a departure with `dep_time_min ≥ 1440`
  belongs to the service night that began the previous calendar day; its
  `date` is the calendar day the departure physically occurred.

## 6. Related identifiers (fill at publish time)

| relation | identifier |
|---|---|
| `is supplement to` | `https://github.com/Tapl1338/miway-findings` (the findings showcase repo) |
| `is referenced by` | weekly findings snapshots (linked from the repo README) |
| `is variant form of` | *(optional)* the repo tag `demo-20260915` or the release that froze the dataset |

## 7. Upload checklist

1. Sign in (GitHub ORCID login works), "New upload".
2. Upload `lateness-sample-250k.csv` **and** `data/README.md` as files.
3. Paste Basic fields (§1), Abstract (§2), Methods (§5).
4. License: MIT. Keywords: §1 list.
5. Add related identifier `is supplement to` → the GitHub repo URL.
6. Communities: consider `zenodo` "Open Aire" none — skip; direct publish.
7. Publish → copy the **concept DOI** (stable across versions).
8. Paste the concept DOI back into: `data/README.md` citation block, the
   resume line, and the fact-pack. Commit + push.
