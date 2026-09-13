# APC Audit — Fleet Infrastructure Package

> **Lineage:** compiled 2026-09-04 from (1) the collector's vehicle-positions
> archive (Aug 17 – Sep 4, 2026) joined against GTFS `trips.txt`, and (2)
> printed fleet-roster pages (Transit 55) snapshotted 2026-09-04 09:30–11:45
> EDT, transcriptions archived privately. Every fleet identification is
> derived from public feed data plus street-visible fleet numbers; no
> agency-internal data is used. §6 is the experiment design as drafted on
> 2026-09-04 (fieldwork status is not part of this package). Promoted to the
> findings lane 2026-09-11. Companions: [APC bias by
> vehicle](apc-bias-by-vehicle.md) and [APC threshold
> brackets](apc-threshold-brackets.md) — the per-vehicle sensor record this
> package explains the structure behind.

**Status:** supporting analysis for the APC (Automatic Passenger Counter) audit.
**Frozen data windows:** collector archive Aug 17 – Sep 4, 2026; Transit 55 roster
snapshots taken Sep 4, 2026, ~9:30–11:45 AM EDT.
**All numbers below are reproducible from the collector's vehicle-positions archive
(`vp_*.json` collections) joined against GTFS `trips.txt`, plus the archived
fleet-roster snapshots (Transit 55, 2026-09-04).**

---

## 1. The problem this package supports

The councillor email's core finding is that MiWay's occupancy data is unreliable:
sensors report in coarse 20% buckets, floors are sticky, flips are missed, and 277
rider check-ins never saw a reading below "20% full." But *which* buses, on *which*
routes, and *why* — that requires knowing the fleet. MiWay publishes no vehicle-level
sensor metadata. This package builds it from public data plus rider observation, in
four pieces:

1. A **translation key** mapping GTFS-RT feed vehicle IDs to printed fleet numbers
   (§2) — without it, no feed observation can be tied to a physical bus.
2. A **per-route artic share** table (§3) — which routes' crowding data rests on
   the least trustworthy sensors.
3. A **fleet census** (§4) — availability and age structure of the fleet.
4. A **garage-territory analysis** (§5) with a designed field experiment (§6).

---

## 2. Fleet ID translation key

**Finding:** MiWay's GTFS-RT `vehicle_id` is *not* the printed fleet number. It is
the printed number plus a constant offset per procurement era. This scheme is
undocumented anywhere in MiWay's public materials.

| Era | Printed series | Feed block | Offset | Verification |
|---|---|---|---|---|
| 2010 Orion VII | 1001–1020, 1031–1045 | 2101–2120, 2131–2145 | +1100 | 1 direct pair + absence-structure |
| 2011 New Flyer XD40 | 1101–1143 | 2201–2243 | +1100 | 1107→2207, 1140→2240 (day-level) |
| 2012 Orion VII | 1201–1215 | 2301–2315 | +1100 | 1202→2302 (day-level) |
| 2013 New Flyer XD40 | 1301–1314 | 2401–2414 | +1100 | inferred (count + structure) |
| 2013 New Flyer XD60 (artic) | 1351–1360 | 2451–2460 | +1100 | 1359→2459 (day-level, 5 dates) |
| 2014 New Flyer XD40 | 1401–1407 | 2501–2507 | +1100 | 1401→2501 (5/5 days) |
| 2017 New Flyer XD40 | 1701–1727 | 2601–2627 | +900 | 1757→2657 (adjacent series) |
| 2017 Nova Bus LFS | 1730–1766 | 2630–2666 | +900 | 1757→2657 (day-level) |
| 2017 Nova Bus LFS Artic | 1770–1799 | 2670–2699 | +900 | 1794→2694 (day-level) |
| 2018 Nova Bus LFS | 1801–1812 | 2901–2912 | +1100 | 1801→2901 (5/6 days) |
| 2019 Nova Bus LFS HEV | 1901–1910 | 2921–2930 | +1020 | 1901→2921 (6/6 days, full-feed search) |
| 2020 New Flyer XDE60 (artic) | 2051–2061 | 2181–2191 | +130 | 2051→2181 (8/8 days) |
| 2021 New Flyer XDE60 (artic) | 2151–2155 | 2195–2199 | +44 | behavioral (2151 OOS since May 24 explains never-seen 2195) |
| 2022 New Flyer XDE40 | 2201–2274 | 3201–3274 | +1000 | 2223→3223, 2263→3263, 2289-family (day-level) |
| 2022 New Flyer XDE60 (artic) | 2275–2290 | 3275–3290 | +1000 | 2282→3282, 2289→3289 (day-level) |
| 2023 New Flyer XDE40 | 2301–2353 | 4301–4353 | +2000 | 2318→4318, 2327→4327, 2341→4341 |
| 2023 New Flyer XDE60 (artic) | 2375–2396 | 4375–4396 | +2000 | full roster match (26/26 seen) |
| 2024 New Flyer XDE40 | 2401–2482 | 4401–4482 | +2000 | 2420→4420, 2444→4444, 2455→4455 |

**Verification method.** A pair is *hard-verified* when the feed vehicle's
day-by-day route history (from the collector archive) matches the printed bus's
"previous blocks served" (Transit 55) on ≥4 dates including at least one multi-route
day. 17 pairs meet this bar. Remaining entries are anchored by series-gap structure
and fleet-count reconciliation.

**Stress test.** Printed numbers collide across eras (1140 vs 2240; both share the
suffix "40"). The offset rule survived this: printed 1140 (2011) → feed 2240,
printed 2240 (2022) → feed 3240, each confirmed by an independent route-history
fingerprint. The rule holds under its hardest case.

**Why the irregular offsets (+130, +44, +1020)?** The 2020/2021 artic orders are the
smallest (11 and 5 buses). Their feed blocks look like leftover ID space — the
feed's allocator appears to assign each cohort a contiguous block, and small late
cohorts got the crumbs. The 2019 HEV block (+1020) sits adjacent to the 2018 Novas'
block, consistent with sequential allocation at delivery time.

**Practical use.** Any bus observed in the feed can now be identified: its model
year, length (artic vs standard), home garage (§5), and — critically — which bucket
model (0–17 pax for 40-ft, 0–28 pax for 60-ft) applies to its occupancy readings.

---

## 3. Per-route articulated share

**Finding:** the routes where crowding is worst are also the routes that run the
highest share of articulated buses — whose sensors are the *least* able to register
the loads that matter.

Artic share = distinct trips operated by a known artic feed ID ÷ all distinct trips
observed, Aug 17 – Sep 4 archive (6 most recent window files):

| Route | Trips observed | Artic share | Audit relevance |
|---|---|---|---|
| 61 Mavis | 116 | **82%** | PM crowding + transfer findings on the worst instrument |
| 66 Mclaughlin | 99 | **77%** | same |
| 5 Dixie | 70 | 60% | |
| 42 Derry | 103 | 52% | watch-list corridor |
| 35 Eglinton | 94 | 44% | |
| 39 Britannia | 59 | 41% | |
| 26 Burnhamthorpe | 91 | 33% | |
| 1 Dundas | 107 | 25% | |
| 103 Hurontario Exp | 60 | 25% | |
| 2 Hurontario | 122 | **20%** | night-crowding headline route — mostly 40-ft, narrower bucket |
| 90, 9, 8, 7, 6, 57, 68, 70, 73, 74 | — | 0% | standard-only |

**Reading:** Route 2's headline finding (buses at/over capacity at midnight) sits on
the *better* instrument — 80% standard buses, floor band 0–17 pax. But the Route 61
PM findings rest 82% on artics whose sensors cannot register anything below ~28
passengers (of a 60-ft vehicle's ~55-seat / ~70-total capacity) — i.e., in exactly
the load range where "how full is it really" questions are asked. **An APC audit
should start where the artic share is highest.**

---

## 4. Fleet census (Sep 4, 2026 snapshot)

~505 listed vehicles across 19 series. Availability measured as "seen in the
collector archive Aug 17 – Sep 4" and "active in the last 3 days":

| Cohort | Size | Seen | Active (3d) | Dead/long-idle (named) |
|---|---|---|---|---|
| 2010 Orion VII | 35 | 32 | ~26 | 1007 (Jul 11), 1009 (Jun 2), 1014 (Jul 27), 1031 (May 14), 1032 (Dec 31 '25), 1033 (Jul 2) |
| 2011 XD40 | 43 | — | 17 active per T55 | — |
| 2012 Orion VII | 15 | 14 | 13 | 1213 (Jun 11) |
| 2013 XD40 | 14 | 13 | 12 | 1308 (**Jun 2023** — retired in place) |
| 2013 XD60 artic | 10 | 8 | 8 | 1351 (Jun 2025), 1355 (May 15) |
| 2014 XD40 | 7 | 7 | 6 | 1402 (Aug 28) |
| 2017 XD40 | 27 | 25 | 25 | 1707 (**Jan 2024**), 1721 (Jun 23) |
| 2017 Nova LFS | 37 | 33 | 33 | 1738 (**Jan 2019**), 1743, 1746, 1750 (Jan 28) |
| 2017 Nova Artic | 30 | 28 | 28 | 1793 (Oct 1, 2025), 1796 (**Oct 15, 2018** — 8 years) |
| 2018 Nova LFS | 12 | 12 | 12 | none |
| 2019 Nova HEV | 10 | 10 | 10 | none |
| 2020 XDE60 artic | 11 | 8 | 7 | 2054, 2056 (both Jul 31), 2058 (Aug 17) |
| 2021 XDE60 artic | 5 | 4 | 4 | 2151 (**out of service since May 24** — 3.5 months) |
| 2022 XDE40 | 74 | 72 | 66 | 2213 (Jun 15), 2266 (Jul 8) + short-term |
| 2022 XDE60 artic | 16 | 14 | 13 | 2275 (Jun 16), 2280 (Jun 30) |
| 2023 XDE40 | 53 | 52 | 52 | 2332 (Aug 12) |
| 2023 XDE60 artic | 22 | 22 | 19 | 2378 (Aug 18), 2380, 2381, 2389 |
| 2024 XDE40 | 82 | 78 | 75 | 2464 (**May 4** — no garage prefix on T55, possible retirement-in-progress), 2454 (Jul 8), 2437, 2452 |

**Headline numbers:**
- **474 distinct vehicles (~95% of the fleet) ran at least once in 2.5 weeks.**
- **~435 (~87%) were active in the last 3 days → ~13% of the fleet unavailable.**
- **Articulated availability: 51/60 (85%)**, worst in the 2020 cohort (7/11).
- 18 confirmed long-term dead, all *predicted by feed absence before T55
  confirmation* (18/18 — the archive and the roster agree perfectly).

**Audit line:** a 2021 artic has been out for 3.5 months and three 2020 artics since
mid-summer. Articulated capacity — the exact capacity the night-crowding asks call
for — was reduced during the entire collection window. Some of what the sensors
report as "crowding" is also a fleet-availability problem.

---

## 5. Garage-territory analysis

Transit 55 vehicle lines carry a home-garage prefix: **CP = Central Parkway**, **M =
Malton**. Mapping all ~505 vehicles:

| Fleet | Garage |
|---|---|
| 2014 XD40, 2017 XD40, 2017 Nova, 2018 Nova | **Malton** |
| 2017 Nova Artic 1770–**1782** | **Malton** (13 buses) |
| Everything 2019 and newer; **all** other artic cohorts; 2010–2013 fleets | Central Parkway |
| Lone M exceptions in CP cohorts | 2249, 2325 (XDE40), 2287 (2022 artic) |

**Territory split (from archive route fingerprints):**

| | Malton | Central Parkway |
|---|---|---|
| Distinct routes served | 24 | 57 |
| Work in top-10 routes | **96%** | 44% |
| Route entropy | 2.29 nats | 3.69 nats |

Malton's fleet is the *old* fleet (2014–2018, 40-ft), doing 96% of its work on the
Westwood Square cluster (107, 5, 51, 39, 7, 11, 30, 15, 16, 22, 24). Central
Parkway runs everything modern, all artics, and the whole city.

**The observation that motivates §6:** 100% of the APC watch-list buses — the
sensors that missed flips, stuck on floors, or showed hysteresis in the August
ground truth (3289, 3282, 2459, 2302, 4318…) — are **Central Parkway** buses. No
Malton bus has ever been sensor-tested in the ground truth. That is a hypothesis,
not a finding — the M side is untested, not proven clean.

**Coupled-system caveat:** because garage determines territory and territory
determines routes, "M artic on Route 5" vs "CP artic on Route 42" is *also* a route
comparison. MiWay's structure (garage → territory → route → duty cycle) means the
garage variable cannot be fully isolated from normal-service data. The experiment
below is therefore a *Malton-conditions* test, and its honest framing is: "does the
floor-stuck behavior appear in Malton's operating environment at all?"

**Geography of the sensor problem:** the worst-crowding routes from the councillor
email — 2 Hurontario, 61 Mavis, 35 Eglinton, 42 Derry — are **all CP territory**.
The routes where crowding is worst are operated by the garage whose buses have the
unverified, worst-behaving occupancy sensors.

---

## 6. Field experiment design (PM rides, Sep 4)

**Experiment 1 — garage comparison (Malton test).**
Ride a Malton-garage 2017 Nova artic on Route 5 (as of Sep 4 morning: 1770, 1772,
1775, 1779 in service; 1784 on Route 39). Record every APC flip with counted
passenger totals. Decision rule:
- M artics flip promptly at plausible thresholds (~17 pax for the 40→20% bands of
  that generation) → the August failures are **garage-linked**, pointing at
  maintenance practice at Central Parkway. Headline: *"the sensor problem is
  concentrated at one garage."*
- M artics stick/floor like CP buses → the problem follows the **sensor
  generation**, not the garage. Headline unchanged, blame shifted to hardware.

**Experiment 2 — new-cohort calibration.**
Ride any 2021 artic (2153 on Route 42 until 26:43 on Sep 4) or 2023 XDE60 (2379,
2388, 2391, 2396 on Route 42). These cohorts have **zero** calibration data; every
witnessed flip pins their thresholds for the first time.

**Experiment 3 — continuity check (conditional).**
2289 (printed; feed 3289), the worst August offender, was on a midday break at last
check. If T55 shows it with a PM block, riding it gives a same-bus before/after
comparison against its Aug 27–29 failure record.

**Tally sheet columns (per stop):** time, stop, boardings, alightings, running
count, APC %, flip? Also note printed number + feed ID on every boarding (each pair
re-verifies or extends the translation key).

**Analysis frame.** Every witnessed flip pins a bucket threshold (e.g., "flipped
20%→40% at N counted pax"). Artic thresholds (28/33/43 pax bands) are the thinnest
part of the calibration; a single good PM ride on a new-cohort artic can add more
calibration data than the entire August artic sample.

---

## 7. What this package does NOT claim

- The garage hypothesis is **untested** until Experiment 1 produces flips.
- "Never seen in feed" is strong evidence of long-term outage over a 2.5-week window
  but includes the collector's own coverage gaps; T55 last-seen dates are the
  confirmation source.
- Artic shares are trip-weighted from a peak-hours-weighted collection window, not a
  uniform sample of all service.
- Occupancy percentages cited anywhere remain raw APC signal, subject to the
  correction method described in the main audit.
