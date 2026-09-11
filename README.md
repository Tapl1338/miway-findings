# MiWay Findings — an independent measurement of Mississauga's bus network

By a Grade 12 student in Mississauga. Built summer 2026, running 24/7 since.

**The question:** MiWay publishes a timetable and a real-time feed. How well does the actual service match what riders are promised — and what would a small, data-driven re-timing buy them?

**The instrument:** a full-stack analytics platform (Python/FastAPI/React) that polls the GTFS + GTFS-RT feeds every 30 seconds, around the clock, on a cloud VPS I administer. As of September 2026 it has logged **56,000+ polls at 98.8% success** and captured **2.9M+ unique scheduled bus departures** for measurement.

---

## What the dashboard looks like

Every finding renders as an interactive view (FastAPI + React, deep-linkable by URL). A few frames, captured live from the running system:

![Home — biggest wins and where to start](docs/screenshots/home.png)
![Service quality — measured lateness, crowding and boardings](docs/screenshots/service-quality.png)
![Councillor brief — the one-pager sent to the ward office](docs/screenshots/councillor-brief.png)
![Changeover impact — the measured before/after of the Sept 8 timetable](docs/screenshots/changeover.png)

---

## What the data shows

Weekly, immutable findings snapshots (each frozen, never edited after freezing):

- [Week of Aug 17–23](docs/findings-v1-n7-aug17-23.md)
- [Week of Aug 24–30](docs/findings-v2-n7-aug24-30.md)
- [Week of Aug 31–Sep 6](docs/findings-v3-n7-aug31-sep06.md)

Recurring findings, stated conservatively:

1. **Early departures.** A large share of recorded departures leave more than two minutes ahead of schedule — and an early bus is a missed bus for anyone following the timetable.
2. **Ghost trips.** A measurable fraction of scheduled trips never appear in the real-time feed at all — for whatever operational reason (breakdown, pull-from-service, gap in the feed), riders waited at a stop for a bus that never came, invisibly. My first published estimate of this rate (1 in 32) was **wrong**; see *The correction* below.
3. **Night crowding.** Some late-evening corridors run their worst decile at or over seated capacity — a rider-safety issue that hides outside rush hour.
4. **Sensor honesty.** MiWay's automatic passenger counters (APCs) report loads in bands far wider than advertised — I characterized the hysteresis from 2.9M observations after 277 on-board check-ins showed two different passenger counts reporting identically.
5. **An equity trap.** The network-level "optimized" schedule quietly makes some wards worse. My own optimizer did this to Ward 9 (+2.56 min/stop) — so I shipped a per-stop guardrail that catches it.

## What a re-timing could buy

The centerpiece is a constraint optimizer (OR-Tools CP-SAT, ~900 lines — [solver_core.py](solver_core.py)) that re-times the network (±5 min/route) under real fleet and layover constraints:

| Measure | Today | After re-timing |
|---|---|---|
| Avg transfer wait (weighted) | 18.84 min | 16.82 min |
| Missed connections | 2,789 | 2,456 |
| Rider waiting | 90,827 pax-min | 81,089 pax-min (**~9,700/day saved**) |

It wins on 100% of 500 simulated days. **The gains are modeled, not field-proven** — the honest framing is "conservative, pending a real-world pilot," and that sentence appears wherever the number does. Full analysis: [councillor brief](docs/councillor-brief.md).

## The correction (the part I'm proudest of)

My first public figure for never-run trips was **1 in 32**. Before anyone challenged it, I found a bug in my own post-midnight trip handling, fixed it, and re-published as **~1 in 60** — with both numbers and the reason kept on the record ([v1 snapshot, finding 2 note](docs/findings-v1-n7-aug17-23.md)). Measurement means your own error rate is part of the dataset. The correction log is public; a `check_claim.py` CLI now greps every published figure against the artifacts before anything is quoted.

## The data, publicly

A 250,000-departure random sample of the observed-lateness corpus (schema, collection method, processing rules, and caveats in [data/README.md](data/README.md)) — download it, run the same computations, check the findings. The full set (3.2M+ departures) is available on request via an issue.

## Operations postmortem

The platform watches its own data age, and on Sept 11 that watch caught a silent three-day sync stall no alert had been configured for — root-caused to a single file-permission bit, fixed in one command, verified within the minute. Written up the same day: [postmortem — lateness sync stall](docs/postmortem-lateness-sync-stall.md). Measurement infrastructure fails the same way measurement does; both get corrected on the record.

## Pre-registration

Before the September 7 schedule change, I committed to falsifiable predictions — written and frozen **before** the post-change data existed, so the analysis couldn't curve-fit: [pre-registration-sept7.md](docs/pre-registration-sept7.md). (It uses seat labels like "alpha-8": the project was built under a multi-agent AI development protocol I directed — task claiming, cross-authored tests, dispute ledgers, a 5→3 right-sizing. I specified what to measure, audited every claim, and own every number.)

## Civic outcome

The findings went to the Ward 9 Councillor's office in August 2026, which **formally referred them to MiWay staff for review** (ongoing).

## Reproducibility

Every figure in the snapshots regenerates from frozen artifacts: SHA-256 evidence manifests, dedup rules pinned as code constants, and regeneration commands in each snapshot's header. 1,200+ backend tests with a CI-enforced coverage floor run on the analysis code. The full platform source remains private while I finish the pilot work; this repository contains the evidence layer.

---

*Not affiliated with MiWay or the City of Mississauga. All analysis is from publicly published feeds (GTFS / GTFS-RT). Questions or corrections welcome via Issues.*

---

*Built and maintained by **Ethan Lin** (Mississauga, ON) under a directed multi-agent AI development protocol — task specification, code review, and every published number are human-owned; see the pre-registration note above for how the work is governed. Data and findings released under the [MIT license](LICENSE).*
