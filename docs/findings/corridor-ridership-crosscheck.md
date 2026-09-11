> **Promoted 2026-09-11 from the project's private analysis repo**
> (`docs/corridor-ridership-crosscheck.md`; frozen as of its stated vintage — numbers are reproducible
> via the scripts named inside, run against the collection described in the
> [data dictionary](../../data/README.md)). Published as-found: early errors
> are kept honestly per the [vintage audit](../ghost-ledger-vintage-audit.md).

# Corridor ridership cross-check — Q1 2026 vs measured data

**Finding: the app's measured data does not corroborate a service-quality
story for the Q1 2026 corridor declines.** Record of the analysis, with the
one exception, so it is not re-litigated.

## The question

MiWay's Q1 2026 Update (May 5 2026, DocumentId=88557 — archived in
`docs/sources/miway_q1_2026_update_extracted.txt`) reports February 2025 vs
February 2026 corridor ridership: most corridors flat, ten down 8–21%
(McLaughlin, Derry worst), Erin Mills up 86%.

If declining ridership were caused by declining service quality, the app's
own measurements should show the big decliners measuring worst on reliability
and/or smallest in ridership. This doc records that they do not, and what
does explain the pattern.

## Method

- Corridor → route mapping from the GTFS `routes.txt` long names (e.g.
  Derry → 18+42, Hurontario → 2+17+103, Eglinton → 35+135).
- Measured boardings: `app/data/boardings_reconstructed_routes.csv` — daily
  lower-bound boardings per route, summed over periods. Rank order only is
  compared (our numbers are lower bounds; absolute ratios to MiWay's figures
  are meaningless).
- Measured reliability: `obs_lateness.csv` via the app's own reader
  (`app.lateness_reads.lateness_base`, 2.25M recorded-departure actuals),
  per-route mean lateness and % of departures >3 min late, weighted by
  observation count when pooling multi-route corridors.
- Service direction: the scraped Sept-7 changes ledger
  (`docs/sources/miway_sept7_service_changes_extracted.txt`).

## Result 1 — Decline vs absolute ridership: no relationship

Spearman ρ = **−0.21 (p = 0.41, n = 18)** between measured daily boardings
and corridor YoY. The biggest decliners are simply MiWay's biggest corridors:
Hurontario (~16.3k measured boardings/day) is at −9% while Mississauga Rd
(~1.4k/day) is at −3%. The decline is broad-based, not concentrated where
riders are (or aren't).

## Result 2 — Decline vs measured reliability: no relationship (one exception)

- Mean lateness vs YoY: ρ = **−0.09**
- % departures >3 min late vs YoY: ρ = **−0.21**

If chronic lateness drove the declines, the −15% to −21% corridors would
measure worst. They don't — McLaughlin (−21%) measures near the top of the
reliability table (−0.22 min mean, 9.1% >3 min late).

**The exception: Hurontario (−9%).** Worst measured reliability of all 18
corridors — 17.6% of departures >3 min late (next worst: 13.8%) and the only
corridor with *positive* mean lateness (+0.39 min) — *and* the highest
absolute ridership. This is the one corridor where measurement and reported
decline point the same direction. Consistent with Hurontario LRT construction
disruption; that route pair is the one to watch in the digest.

## Result 3 — Sept-7 service changes treat the declines as demand-side

Of the 10 biggest decliners, **one lost service**: 18 Derry (AM/PM peak
headways widened 15 → 18-20 min), with MiWay's stated reason: *"Due to
reduced ridership. MiWay realigns resources to high-demand routes."* Five of
the ten got **more** service on Sept 7 (McLaughlin, Mavis, Dixie, Eglinton,
Kennedy). MiWay's own actions read the declines as demand-driven — matching
what the measured data shows.

## Caveats (why this isn't stronger than it is)

- Our reliability measurements are Aug–Sep 2026: they show whether quality
  *currently* penalizes these corridors, not what caused a Feb 2025 → Feb
  2026 decline. A quality episode inside that window that has since healed
  would be invisible here.
- The Q1 percentages are board-period windows (the sources README's
  normalization caveat applies).
- "Derry −21%" almost certainly means the 18 branch; 42 Derry is a top-2
  system route (10,750 published boardings) and is not plausibly down 21%.
- Boardings lower bounds support rank-order comparison only.

## Bottom line

17 of 18 corridor declines are corroborated by nothing in the measured data
except that MiWay acts on them (the Derry cut) — broad-based, uncorrelated
with ridership level or reliability. **Hurontario is the single corridor
where the measurements agree with the reported decline.** Anyone treating the
corridor table as evidence of a system-wide quality collapse is going beyond
what either MiWay's data or this app's data supports.
