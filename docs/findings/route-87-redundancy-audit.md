# Route 87 Skymark cancellation — redundancy-claim audit

- **Frozen:** 2026-09-05. Immutable.
- **Claim audited:** MiWay cancelled the 87 Skymark effective 2024-09-02 as
  "service redundancy" (City service-change announcement, Aug 2024).
- **Evidence vintages** (all in the project's frozen GTFS archive (Wayback Machine vintages; SHAs on file)):
  `miway_gtfs_2017-02-28_wayback-2017-vintage.zip` (sha16 `8ccdd201dcd9b44e`),
  `miway_gtfs_2023-03-19_wayback.zip` (sha16 `f3fec2cbe43ee7ba`),
  `miway_gtfs_2024-01-17_wayback.zip` (last pre-cut vintage, retrieved from
  the Wayback Machine 2026-09-05), and the current live feed.

## Verdict in one line

The redundancy claim is **literally true at the stop level but misleading at
the schedule level**: every one of the 87's 65 stops had an alternative
route, yet the *combination* deleted the only bell-time pass covering the
author's secondary school's morning trip — coverage that existed in the
pre-cut system twice over.

## What each vintage shows

| Vintage | 87 service | 38's southbound bell pass (stop 3023/3053) | Bell coverage |
|---|---|---|---|
| Feb 2017 | Full-time: 54 weekday trips, ~20-min AM Creditview headways | 07:55-ish window (08:16 at Bristol) | 87 covers bell; 38 supplements |
| Mar 2023 | **Already peak-only: 14 trips/day** (04:58–09:15, 15:46–20:01) | 07:46, **08:10** | 87 (~08:08 at Bristol) + 38 (08:10) — double coverage |
| Jan 2024 (last pre-cut) | Peak-only: 14 trips/day, same shape | 07:58, **08:04** | 87 (08:08 Creditview/Bristol) + 38 (08:04) — double coverage |
| Sept 2024 → | **Cancelled** ("service redundancy") | 2026 feed: 07:51, then **08:22** — 31-min hole | **Nothing covers the 08:17 bell** |

## The three findings

1. **Stop-level redundancy: TRUE.** In the Jan 2024 feed, 0 of the 87's 65
   stops were served by no other route. MiWay even published the full
   replacement mapping stop-by-stop in the service-change notice (Transit
   Toronto, 2024-09-01). Every stop had *a* bus.

2. **Schedule-level redundancy: FALSE for the bell.** The replacement
   routes exist, but none of them ran the 87's bell-time pass at the 87's
   times. The 38's own southbound pass drifted *earlier* across vintages
   (08:10 → 08:04 → 07:51), moving away from the 08:17 bell, while the 87's
   Creditview pass (07:55 in 2017, 08:08 in 2023–24) was the one holding
   the bell. The cut removed that pass and nothing shifted to replace it:
   net effect is a 31-minute weekday hole (07:51 → 08:22) straddling the
   08:17 bell in the current feed.

3. **Asymmetric treatment in the same service change.** The same Sept 2024
   change *resumed* high-school specials for Rick Hansen (314/315), Philip
   Pocock (302/307), Streetsville (306/313), Stephen Lewis (321) —
   including a "314 Rick Hansen - Creditview" special that starts at the
   author's school's own stop — while the 87's general-service bell pass on the same
   corridor was deleted with no backfill. School demand on Creditview was
   deemed worth an extra for one school's riders and not for another's.

## Honest framing (author-concurred)

- The 87's Skymark/airport-alignment ridership was genuinely low; the author
  (daily rider, Ward 9/5 Creditview corridor) concurs the cut itself was
  defensible. By 2024 the route was already whittled to peak-only.
- The harm was **collateral and narrow**: bell-time coverage on Creditview.
  The fix is correspondingly narrow — one ~08:05 tripper on the existing 38
  restores what a 14-trip route provided. This is not a "restore the 87"
  ask; it is a "backfill the one pass that had no replacement" ask.
- Prediction registered for v4 collection: AM crush loads on the 07:51
  38 trip (resolvable above the ~13-pax APC floor) and elevated lateness
  on the 08:22 trip. If confirmed, the case is measured, not anecdotal.

## Sources

- Feed vintages: the project's frozen GTFS archive (Wayback Machine vintages; SHAs on file) (SHA-256s on file in the project archive manifest).
- City service-change announcement (Facebook/citymississauga, Aug 2024):
  routes 76 and 87 "cancelled as service redundancy"; 87 "weekday rush
  hour only" at cut time.
- Transit Toronto, "MiWay revises routes and services, September 2"
  (2024-09-01): the stop-by-stop replacement mapping quoted in finding 1,
  and the school-special resumptions quoted in finding 3.
- Author rider log, 2026-09-06 (leave-home 7:35 in grade 9,
  7:10 now; 38 passes 07:51/08:22 vs the 08:17 bell).

## Addendum — the PM mirror proof (2026-09-05, author observation)

Author report: the afternoon 38 is well-timed (~2:35 vs the 2:20 dismissal)
but the morning has two northbound passes and no timed southbound.
Feed verification (current pre-Sept-7 feed, weekday service at the school
stops 3023 SB / 3053 NB):

- **PM (2:20 bell):** 38 SB at 14:32/14:41, 38 NB at 14:34 — passes land
  12–21 min after the bell, matching release-and-walk lag. Bell-timed.
- **AM (8:17 bell):** 38 NB at 08:02 **and** 08:07, 314 NB (school
  special) at 08:05 — but the school-arrival direction (SB) has NOTHING
  between 07:51 and 08:22.

The inverse symmetry is the proof: in the PM the school direction gets
the bell-timed pass; in the AM the *away-from-school* direction gets two
well-timed passes while the school direction gets zero. MiWay's planners
 demonstrably know the bell times to the minute — the AM hole is an
 unaudited morning side, not an unknown school. This removes the last
 innocent explanation for the gap and strengthens the one-tripper ask:
 the PM proves the capability and the knowledge; only the AM was never
 checked after the 87's bell pass was deleted.

Author addendum 2 (2026-09-06, feed-verified): the AM 08:07 NB pass is a
**garage pull-out**, not scheduled service — trip 30463243 originates
07:44 at Central Pkwy At Semenyk Crt (Central Parkway Garage's street),
skipping the Cooksville GO → Erindale segment the normal 38 trips cover
(07:32 origins from Cooksville Platform 6). The one usefully-timed AM
pass exists as a byproduct of garage positioning, pointed away from the
school — planned bell-timing appears in the PM only. And the 314 Rick
Hansen special (08:05) **originates at the author's school's own stop** (3053):
a school extra launches from this school's curb toward the other school,
while the school it departs from has no bell-timed pass of its own.
