# MiWay Transfer-Sync Tool — Councillor Brief (one page)

<p align="right"><img src="demo-qr.png" width="110" alt="QR: interactive demo" /><br /><sub><b>Try the interactive demo</b> — scan or visit<br /><span style="font-size:8pt">tapl1338.github.io/miway-findings/demo</span></sub></p>

**What this is.** A data tool that analyses MiWay's published timetable,
identifies every scheduled transfer connection in the network, and surfaces
where riders face the worst waits — the stops with 20+ minute transfer gaps,
the most-circuitous routes, the equity gaps between wards. On top of this
analysis, a solver proposes small re-timing shifts (±5 minutes per route) that
could reduce the worst transfer waits. The analysis works without the solver;
the solver is a bonus.

This page reports what the tool actually found on the real schedule. All numbers
regenerate from `backend/scripts/` (see `docs/README.md` for the exact
commands, run with `--max-connections 6000` so the reports match what the
dashboard shows).

**The setting studied.** Weekday service 06:00–22:00 ("all day"), 6,000 capped
transfer connections (the dashboard's own analysis cap), weighted by real
average-weekday boardings (published APC where available, calibrated estimates
elsewhere). Run of record generated 2026-08-23, re-pinned to the unified
`--time-limit 120` basis 2026-08-24; canonical values in `RUN-OF-RECORD.md`,
machine-readable sources `exec-summary.json` and `equity-report.json`.

## What the tool found — the honest picture

| Measure | Today's schedule | After tool's re-timing |
|---|---|---|
| Average transfer wait (min, weighted) | 18.84 | 16.82 |
| Missed connections | 2,789 | 2,456 |
| Passenger-minutes of waiting (06:00–22:00) | 90,827.0 | 81,089.3 |
| Passenger-minutes saved | — | **~9,700/day** |

**The headline is honest: ~9,700 passenger-minutes of waiting saved per
weekday (~9% of rider-wait)** on a static schedule model. Two identical-config
solver reruns (unified `--time-limit 120`, post phantom-filter model) agree
at 9,737.7 vs 9,737.6 pax-min (within 0.01%), so quote it rounded. Older
pre-unified runs ran far lower (a ~3,400/day figure briefly circulated from
an uncapped-connections run); do not mix vintages.
This is a modelal savings depend on actual
on-time performance, which a pilot would measure. The ridership and farebox
projections from the exec summary are **not included here** because they rely
on literature elasticities that haven't been calibrated to MiWay. If council
wants those figures, they should be treated as planning-order-of-magnitude only.

**Where it *also* helps is the worst cases.** The tool's sharpest, most
defensible output is identifying the worst single misses — e.g. Eglinton & Dixie,
where the 35→7 transfer carries a 14-minute scheduled wait against a 24.8-minute
headway (`validation-report.md` §4 has the ranked list; the dashboard's
"Top missed connections" view regenerates it live against any feed).

No schedule is ever perfect, but these are the transfers that leave real people
standing for a quarter-hour plus.

## Two honest caveats

**1. On-time performance erodes the gain.** Re-timing tightens transfers toward
the 2-minute floor, which is optimal *on paper* but sensitive to lateness.
The worst-case model (each bus independently late; common-mode lateness cancels):

| Mean lateness | Expected saved vs today |
|---|---|
| 1 min | +4,280 min |
| 2 min | +2,867 min |
| 3 min | +1,862 min |

The plan keeps beating today's schedule until buses average ~**9.75 minutes of mean
lateness** in this model. Driven by real observed lateness instead
(`validation-study.md`: 338,667 observed GTFS-RT departures, all-period
all-period bootstrap, 500 simulated days), it wins on **100% of simulated
days** (median +785 net
saved/day) — every simulated day, though the realized gain never matches the deterministic paper gain, and the reports say so.

**2. Winners and losers are specific and named.** The network gains while some
individual stops lose — Ward 9 currently nets slightly worse under the
unconstrained plan (`ward-9-brief.md`). Any pilot needs a stop-level guardrail;
that is the recommendation below.

## Measured context — one week of live bus data

An always-on collector has been recording MiWay's real-time feed since
2026-08-17 (six days, all periods; `service-quality-brief.md`). Three
measured findings frame the re-timing case: **buses leave early constantly**
(21–38% of daytime departures run >2 min early — route 51 on half or more),
**reliability decays through the day** (>5-min-late share rises from 1.8% at
07:00 to 7% by 22:00), and **Saturday is a different network** (demand
~half of weekday, missed-trip rate 7.9% vs 1–4.6% on weekdays). The
re-timing pilot and the schedule-padding recut attack the first two; the
Saturday ghost rate is the frequency/reliability conversation.

## What we recommend before anything operational

1. **The ground-truth validation is done at the model level** (real MiWay
   GTFS-RT lateness through the same model — see `validation-study.md`). The
   remaining field step is a **pilot** that measures actual transfer volumes
   and waits at the flagged connections — that is the implementation plan's
   first deliverable.
2. **Guardrail the equity.** Add a no-stop-gets-worse constraint before any
   pilot, so network savings can't be bought by making named stops worse.
3. **Never present the on-paper numbers as realized savings.** Report them
   only alongside the lateness sensitivity and the real-data Monte Carlo
   above — that is the defensible version.
4. **The pilot is cheap in service, costs staff time.** Re-timing adds no buses
   or drivers, but the pilot needs ~0.25–0.5 FTE analyst time over 6 months
   plus a scheduler's partial time to import the re-timed `stop_times.csv` and
   reconcile rosters — tens of thousands of dollars, reversible (see
   `implementation-plan.md` §"Pilot cost").

**Bottom line.** A credible re-timing proposal: ~9,700 passenger-minutes of
wait saved per weekday, staying positive until ~9.75 min mean lateness in the worst-case
model and winning all (100%) of simulated days driven by real observed
lateness — with the losers named up front and a guardrailed pilot as the ask.
The remaining honest caveats are the model-on-model projections (ridership,
farebox) and the need to verify actual transfer demand in a pilot before
committing.

## External standards and sources (for follow-up questions)

Every measured claim in this package can be checked against a published
standard or MiWay's own documents.

**On-time window (early departures)**

- MiWay's own definition, per the 2022 Transit budget submission: schedule
  adherence was historically counted at -2/+7 minutes, and in 2019 was
  aligned to the industry standard of **-1 minute early / +5 minutes late**
  (mississauga.ca, D_MiWay_2022_Budget.pdf). Departures more than two minutes
  early fail even the older, looser window.
- Industry consensus matches: TCRP *Minutes Matter* bus reliability guidebook
  reports 1-early/5-late as the most common North American window; TCRP
  Report 165 proposes 0/+5 because riders time themselves to the schedule.
- Saberi, Zockaie, Fang & El-Geneidy (*Journal of Public Transportation*):
  "For a passenger arriving shortly before a scheduled bus departure, an
  early departure is equivalent to a bus being delayed a full headway."

**APC sensor accuracy**

- US FTA/NTD rules: APC data may only be used for reporting after validation
  against manual ride checks; the error adjustment factor must not exceed 9%,
  with an annual maintenance study of at least 100 trips (USF CUTR, *Guidebook
  on Using Automatic Passenger Counters for NTD Reporting*).
- US industry practice targets APC counts within +/-5% of manual counts; the
  European VDV 457 standard requires <=2% error per 1,000 passengers,
  third-party audited (Mass Transit magazine, "Defining APC Accuracy
  Standards in North America").
- Peer-reviewed baseline: Kimpel, Strathman et al., Tri-Met APC evaluation
  (*Transportation Research Record* 1835) - even well-regarded systems show
  systematic bias and need correction factors. The ride-along findings in
  docs/councillor-email-draft.md (one display reading "20% full" anywhere
  from 5 to 29 passengers) exceed any of these tolerances by an order of
  magnitude.
- Cut by vehicle, three buses account for most of the failures in the 277
  check-ins: vehicle 3289 missed all 4 of its qualifying load changes,
  vehicle 2302 missed 4 of 6, vehicle 2240 missed 4 of 5
  (`backend/app/data/apc_bias_by_vehicle.csv`, regenerable via
  `scripts/apc_bias_by_vehicle.py`) - an audit has a concrete starting list.

**Measured transfer waits at Meadowvale Town Centre (observed lateness)**

- Feeding MiWay's own recorded lateness (near-real-time observations,
  horizon ≤ 1; 715,220 rows on the frozen cut, cut-dependent) through the
  terminal's timetable (schedule side filtered to the canonical 2026-08-18
  timetable block): departure-weighted average wait is ~14 min realized vs
  ~13.5 scheduled (DEC-09 errata), and the tails are severe - on eleven
  regular pairings into Route 43, one transfer in ten already means a
  38-41 minute wait and over half fail entirely (51-66% missed shares)
  under observed conditions (`realized_waits.csv`, `scripts/realized_waits.py`;
  school-special pairings are worse still). Re-timing targets exactly this
  tail.

**Late-night service demand and crowding**

- MiWay 2025 Report to the Community: Five Plus consultations heard that
  riders most want "more frequent service, better reliability, and service
  that runs later at night and more often on weekends"; overcrowding on the
  busiest routes dropped 54% in 2025 under targeted frequency investment;
  on-time performance was 73%.
- The Hazel McCallion LRT will not relieve Hurontario for years: Metrolinx
  now targets construction completion ~2027-28 with opening after testing
  (Global News, Apr 2026; CityNews, Aug 11 2026; original target was 2024).
  Until then, Route 2 carries the corridor's full load -- which is exactly
  the period the midnight crowding data covers.
- MiWay 2024 Report: Council approved an 8% service increase explicitly to
  answer "overcrowding, inability for some passengers to board and reduced
  reliability."
- Mississauga TRIP Technical Report (2025): the city and Peel target 55%/50%
  sustainable mode share by 2041; reliability is a stated precondition.
- OC Transpo publishes monthly downloadable KPIs including excess wait time
  and on-time performance by service class
  (octranspo.com/en/about-us/performance-measures/) -- the publication model
  the "resume publishing" ask mirrors.
- MiWay 2022 Budget: a 2% service-hour increase = 31,000 hours at a net
  impact of $1.14M rising to $2.88M -- roughly $35-70 per new service hour,
  the unit rate used to price the pilot asks.

**Ghost trips / missed scheduled trips**

- Stateline (Pew, Jan 2023): national "ghost bus" investigation; TransitCenter:
  "You can't fix what isn't measured," and agencies should publish cancelled-
  trip statistics.
- Swiftly + Cal-ITP ETA Completeness Benchmark: first standardized ghost-trip
  metric; >=95% of scheduled trip-stops carrying real-time information is
  best-in-class; about half of North America's largest agencies score below.
- Precedent for citizen methodology: Chicago's volunteer ghostbuses.com and
  the UChicago Mansueto Institute "StopWatch" study (110M+ real-time pings)
  used the same real-time-vs-schedule comparison as this project's collector.
- This project now keeps a running per-date ledger of ghost totals
  (`backend/app/data/ghost_ledger.csv`, via `scripts/ghost_trips.py --ledger`)
  so the "one in N" figure can be refreshed on demand rather than re-derived.
