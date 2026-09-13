# Sept 7 changeover — the definitive schedule diff (26AU03 vs 26SE07)

> **Version:** 1 (2026-09-12) · **Data:** static GTFS, one published zip
> (SHA-256 `f43fb0a9de891dbd…`) · **Method:** weekday service compared by
> `service_id` period prefix (26AU03 vs 26SE07); full method notes at the
> end. Companion to the measured before/after: [the retime win at school
> stops](school-stop-retime-win.md).

**Status:** complete. **Source:** one MiWay GTFS zip, SHA-256
`f43fb0a9de891dbd…` — byte-identical across 2026-08-19 (earliest local
evidence), the Aug 23 archive, and the live vendor download on 2026-09-07.
MiWay publishes **one combined-period zip** (feed 20260805–20261025) with
every service period inside; the Sept 7 change is purely calendar-driven
(`calendar_dates.txt` switches from 26AU03 rows to 26SE07 rows). The diff
below was therefore computable three weeks before the change took effect.
Compared: weekday service (`service_id` contains `Weekday`), 26AU03 active
Aug 5 – Sep 4, 26SE07 active Sep 8 – Oct 23. Holidays excluded from both
sides. Reproducible from any copy of the zip; see method notes at the end.

## Network-level (weekday)

| Metric | 26AU03 (Aug) | 26SE07 (Sept) | Δ |
|---|---|---|---|
| Weekday trips | 5,423 | 5,589 | **+166 (+3.1%)** |
| Weekday stop-visits | 206,651 | 210,690 | **+4,039 (+2.0%)** |
| Routes (core + specials) | 57 | 67 | +10, all 3xx school specials |
| Stops served | 3,082 | 3,130 | **+61 gained, −13 lost** |
| Service span | 02:00–27:44 | 02:00–27:44 | unchanged |

**Headline: this is an expansion, not a redesign.** The route set is stable
(no route dropped, no core route added — the 10 "new" routes 302–321 are
1–5-trip school specials), the span is identical, and the growth is
concentrated in a handful of corridors. This matches the shape of the
May 2024 council announcement (57,000 added hours targeted at 126, 44/110
UTM, 11 Westwood, 61 Mavis, 66 McLaughlin) — though see route 61 below.

## Per-route changes (weekday trips / stop-visits)

**Cuts:**

| Route | Trips | Stop-visits | Per-terminal median gap | Notes |
|---|---|---|---|---|
| **18** | 90 → 61 (−29) | 3,060 → 2,073 (−987) | 15 → 19 min | the cut **widens the existing midday hole**: the route already had a 10:00–12:00 dead zone (163-min gap 09:37→12:20); Sept 7 removes the 12:20–13:59 lunchtime bridge (12 → 0 trips), stretching the no-service stretch to 300 min (09:30→14:30) |
| **61** | 189 → 182 (−7) | 6,500 → 6,276 (−224) | ~unchanged | trimmed despite being named in the 2024 release |
| 109 | 162 → 160 (−2) | 3,240 → 3,200 (−40) | — | noise |

Route 18 structural detail: same two patterns (both directions, same
endpoints, span unchanged 04:45–19:38), simply fewer of them. The route was
**never all-day** — the August schedule already skipped 10:00–12:00 — and
the cut removes the short lunchtime recovery block that partially bridged
it, doubling the longest gap from ~2.7 h to 5 h.

Gap-context note (hourly audit of all routes, both weekday blocks pooled):
route 18 is the **only** route whose longest departure gap moved materially
(every other route: ≤14 min change). Peak-only patterns are common on this
network — routes 108 (~5 h), 43 (~4 h17), 15 (3 h), and even 126 (3 h20
after its gains) run comparable or longer gaps — so the 18's hole is
notable only because the route previously had a lunchtime bridge and lost
it, not because a midday hole is unusual.

**Gains** (headway = trips-weighted mean of per-terminal median gaps —
see method note; the naive all-direction pooled median understates gaps
~2× and produces false collapses when branches pulse):

| Route | Trips | Stop-visits | Per-terminal median gap |
|---|---|---|---|
| **110** | 118 → 171 (**+53**) | +608 | 21 → **12 min** (−9) |
| **126** | 49 → 72 (**+23**) | +334 | 20 → **14 min** (−6) |
| **44** | 102 → 124 (**+22**) | +673 | 24.5 → 19 min (−5.5) |
| **108** | 26 → 31 (+5) | — | 25.5 → 20 min (−5.3) |
| **26** | 156 → 168 (+12) | **+824** | 15 → 14 min |
| 8 | 61 → 69 (+8) | +327 | 37.5 → 36 min |
| 2 | 220 → 226 (+6) | — | — |
| 13 | 97 → 103 (+6) | — | — |

**Not headway changes, despite appearances:** routes 46 and 36 each show
big pooled-gap collapses (31→8, 17→6.5) that are pure branch-timing
artifacts — 46's two branches leave their two terminals 5 min apart
(both branches unchanged at ~44 min per-terminal median, +2 one-off
midday school trippers), and 36's two branches moved to a same-minute
pulse off their terminals (per-terminal ~41–42 min unchanged). At any
actual stop, the wait barely moved on either route. Likewise every
per-terminal number above is a per-direction headway — roughly double the
naive pooled figure.

Every other core route moved by ≤4 trips. Slight loosening: 18 (15→19,
see cut), 53 (21→22.5), 49 (31.6→33.3), 46 (+1, noise).

## Stops gained and lost

61 stops gained, 13 lost on weekdays. The gained set is dominated by the
new 3xx school specials (Central Pkwy corridor, Second Line West/Sombrero,
Mississauga Valley Daralea, Vista Blvd, Ceremonial Dr) plus real additions
on core routes (e.g. Huron Park Access Rd on route 4).

The **13 lost stops are, without exception, consolidations — not coverage
removal.** Every lost stop has a same-route replacement within 230 m in
the SE07 period (checked by name-match, id-match, and lat/lon proximity;
the naive "lost/gained" diff flags these because a moved stop gets a new
stop_id):

| Lost stop | Nearest SE07 stop, same route | Dist |
|---|---|---|
| 1099 South Common Platform A (26) | Platform B / Platform E (26 switched platforms) | 19–20 m |
| 9162 Aukland Rd N of Dundas (3) | 1304 same-name directional pair (1, 3, 307) | 59 m |
| 1011 Meadowvale Blvd W of Syntex (38) | 1060 Meadowvale Blvd E of Rapistan | 90 m |
| 2408/2428 Falconer/Matlock (44) | 2407 Queen St At Matlock (43, 44) | 108–131 m |
| 2410 Falconer At Hyde Mill (44) | 2490 Falconer N of Plainsman | 113 m |
| 1709 Mississauga Rd S of Badminton (44) | 2356 Mississauga Rd S of Badminton | 124 m |
| 0677 Central Pky S of Burnhamthorpe (38) | 0659 Central Pky At Golden Square | 149 m |
| 0713/0735 Tedwyn Dr At Munden (4) | 0712 Tedwyn Dr At Chantenay | 162–180 m |
| 0654 Creditview At Shagbark (38) | 0658 Creditview At Burnhamthorpe | 165 m |
| 1702/1705 Mississauga Rd (44) | 1751 Mississauga Rd At Montcrest | 162–226 m |

So the Sept 7 change bundled a **stop-spacing optimization** — fewer,
farther-apart stops on 38, 44, 4, and the 26 terminal — alongside the
frequency additions. Riders at a consolidated stop walk at most ~230 m
(2–3 minutes). Earlier boardings-proxy alarm on 0654 Creditview/Shagbark
(est. 1,240 over three weeks, 15× network median) is real *usage* at that
exact curb, but the replacement stop is 165 m away on the same route — a
walk, not a lost connection. The one to keep an eye on is the 44
Mississauga-Rd corridor: three stop pairs consolidated in one pocket, so
the walk penalty compounds for riders between them (worst case two
adjacent consolidations ≈ 400 m extra walking). This is a deliberate
speed-vs-access trade, and whether it was the right one is a ridership
question our collector can eventually answer.

(For the record: an earlier revision of this analysis called 0654 a
"genuine red flag" and framed the 13 as culls-vs-left-behind. That reading
treated stop_id churn as coverage loss. The proximity check above is the
correction — and a standing lesson: **a stop "lost" in id-space is not a
stop lost in street-space until you've checked what serves it now.**)

## What this diff can and cannot tell

Can: exactly what the agency planned to change, three weeks early, to the
trip. Cannot: whether vehicles actually ran it (that is the collector's
measured before/after — the changeover panel), who it serves (ridership),
or whether the 3xx specials are publicly rideable (school trips are often
loaded in the public feed regardless).

The one genuinely unknown question the zip cannot answer — and the reason
the survival probe existed — is whether the vendor's real-time engine
followed the new period correctly on day one. Static GTFS is a plan;
GTFS-RT is the test of the plan.

## Method

`trips.txt` joined to `calendar_dates.txt` (exception_type=1) classified by
service_id prefix (26AU03/26SE07) and day-type token; `stop_times.txt`
parsed to per-trip first departure / last departure (GTFS times >24 h kept
as minutes past service-day midnight). Headway = trips-weighted mean over
terminals of the median sorted first-departure gap per (route, terminal) —
per-direction, so it reads ~2× the naive pooled figure; the pooled variant
was rejected after it produced false collapses on 46/36 (branch pulse
timing, not frequency). Stop sets = union of stop_ids over weekday trips
per period. Boardings proxy = positive `net_flow_pax_cap65` from the
collector's APC boardings pipeline, mapped to stops via
(trip_id, stop_sequence) through the AU-period `stop_times.txt`, cumulated
over the observation window; subject to the project's known
APC-quantization caveats (20%-bucket floor; zero-flow rows may be
sub-bucket). The archived `miway_gtfs_2026-08-23_pre-sept7.zip` (see the
archive MANIFEST) is byte-identical to the live vendor download — the
"pre-sept7" name is a misnomer, kept for continuity with the capture
protocol.
