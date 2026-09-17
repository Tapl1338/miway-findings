# How every number is measured

> **Version:** 1 (2026-09-12) · **Purpose:** the methodology companion to
> the findings index — what the data is, how it becomes a number, and the
> checks that keep a retired number from hiding in a published page.
> **Provenance:** maintained in the private repo's `docs/methodology.md`;
> this copy is verified token-for-token against it on every push (see
> *Verification layers*).

## The data

Everything starts from **publicly published feeds**: MiWay's GTFS schedule
and its GTFS-RT vehicle positions, collected continuously since summer
2026 (24/7 on an always-on collector; every snapshot SHA-256-manifested).
On top of the feeds sit **399 manually collected ride-along check-ins**
(Aug 18 – Sep 12, 20 vehicles, 14 routes; 277 collected in the core
Aug 18–21 window): a human count of passengers paired
with what the bus's occupancy display claimed at the same moment. The
manual log is what makes the sensor findings possible — without a
ground-truth count, "the display said 40% full" is unfalsifiable.

## How a number is made

Three measurement families, each with its own pipeline:

| Family | Method | Example |
|---|---|---|
| **Schedule vs realized** | Timetable-derived trip flags and windows diffed against observed vehicle movements | School-door early departures 62% → 39% |
| **Sensor honesty** | Manual count ÷ displayed bucket ⇒ implied thresholds, per vehicle; display-lag measured against real load changes | 72% of qualifying load moves (44 of 61) produced no display change |
| **Network structure** | Feed-only arithmetic: pairings, headways, segment runtimes, stop access | 61,526 segment-pairs audited, 277 flagged |

The optimizer's figures (e.g. ~9,700 rider-minutes/day) are a fourth
family: **modeled, not measured**. That sentence appears wherever the
number does, and the pre-registered validation study is the honest
boundary of the claim.

## Pre-registration

Before the September 7 schedule change took effect, predictions were
written and frozen **before** post-change data existed — so the analysis
could not curve-fit. The predictions, the scoring, and one deliberately
published partial miss live in [the pre-registration
note](../pre-registration-sept7.md).

## Verification layers

A published number has to survive four independent checks:

1. **Vintage manifests** — every collection snapshot is hashed on arrival;
   dedup rules are pinned as code constants, so "which rows existed when"
   is reconstructable. The governing rule after the ghost-ledger audit:
   **never delete bad rows — stamp them.**
2. **Test-gated analysis code** — 1,200+ backend tests with a CI-enforced
   coverage floor run on everything that computes a published figure.
3. **The drift gate** — every promoted document is diffed token-for-token
   against its private twin: every number in the source must appear in the
   public copy. The check runs daily on the private side and on **every
   push to this repository** (CI), so a regenerated source cannot leave
   retired numbers published unnoticed.
4. **Data-vintage staleness alerting** — the sources behind the dashboard
   are age-checked continuously; a stalled pipeline emails within a day
   instead of surfacing weeks later as an unexplained gap.

## What this means for citing

* Numbers labeled **measured** (retime win, APC bias, crowding,
  corridor audits) come from the pipelines above and carry their evidence
  tables in the linked findings.
* Numbers labeled **modeled** (optimizer gains) are simulation results
  under stated constraints — cite them as "conservative, pending a
  real-world pilot."
* Corrections: published findings are re-litigated in public rather than
  quietly edited — see the corridor-decline cross-check for the pattern.
  Questions or corrections via Issues.

*All analysis is from publicly published feeds (GTFS / GTFS-RT) plus the
project's own manual ride-along log. Not affiliated with MiWay or the
City of Mississauga.*
