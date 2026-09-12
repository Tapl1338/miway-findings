# Route 34 Credit Valley cancellation — redundancy-claim audit

- **Frozen:** 2026-09-07. Immutable.
- **Claim audited:** MiWay cancelled the 34 Credit Valley effective 2024-02-26
  "due to low customer demand. The resources from this cancellation will be
  reinvested in Route 35" (City service-change announcement, Feb 5 2024;
  corroborated by Transit Toronto, 2024-02-22, and reddit/insauga coverage).
- **Evidence vintages:** the project's frozen GTFS archive (Wayback Machine vintages; SHAs on file) — 2017-02-28,
  2023-03-19, 2024-01-17 (last full month of 34 service), and the current
  live feed (SHA-256s on file in the project archive manifest).

## Verdict in one line

The cancellation itself is procedurally the cleanest of the post-2020 cuts —
announced in advance, stop coverage preserved (93% plus near-site
replacements for the rest) — but the **reinvestment claim fails the
schedule test**: the 35 runs *fewer* weekday trips today (159) than the day
the 34 was cancelled (175), so the "resources reinvested" cannot be found
in the timetable 2.5 years later. The "low customer demand" premise is not
checkable from GTFS and remains unverified.

## What each vintage shows

| Vintage | 34 service | 35 weekday trips |
|---|---|---|
| Feb 2017 | 483 trips (all services) — full-time | — |
| Mar 2023 | 428 (all services) | — |
| Jan 2024 (last month) | **64 weekday trips, ~3–4/hour (≈15-min headways) 04:00–21:00** — genuinely full-time | 175 |
| Aug 2026 (26AU03) | 0 | 159 |
| Sept 2026 (26SE07) | 0 | 159 |

## The three findings

1. **A different cut profile from the 87.** The 87 was starved to 14
   peak-only trips before cancellation — slow decay then removal. The 34
   was killed while still running 15-minute headways all day. Whatever the
   ridership truth was, "the route had already withered" is *not* available
   as a defense here, unlike the 87.

2. **Stop-level coverage held.** Of the 34's 89 stops, 83 (93%) are still
   served today. The 6 uncovered stops all have served replacements within
   281 m (five are Eglinton Ave consolidations near 35's alignment —
   1896/1897/1807; one is a Tenth Line platform swap to 3529, served by
   321). No bell-time or single-pass hole analogous to the 87's Creditview
   finding surfaced in this check. The 35 is the dominant substitute
   (serves 47 of the 89 stops), followed by 68, 9, 46.

3. **The reinvestment claim fails on trips: 175 → 159 (−9%).** The 35 runs
   fewer weekday trips in 2026 than in Jan 2024, when the 34's "resources"
   were supposedly reinvested into it. Caveats: reinvestment could
   nominally have gone to span, school specials, or reliability rather
   than trip count — but a −9% trip change is the opposite signature of an
   infusion. Note also the 35's Jan-2024 figure is CPBlock-only (its
   MABlock had no weekday service); like-for-like on weekday totals.

## Honest framing

- "Low customer demand" is **unverifiable from public data** — this is
  precisely the precision-ceiling problem: GTFS shows supply, never load.
  The 2024-era APC/boardings data that could audit the claim is exactly
  what the data-ask seeks. If MiWay's claim was true, this audit ends
  here; if it wasn't, only tap-level history could prove it.
- Circumstantial counter-signal: a route MiWay kept at 15-min all-day
  headways into its final month does not look like an obviously dying
  route, and demand claims made without published load data deserve the
  same skepticism as the 87's "redundancy" claim (which was literally
  true and misleading at once).
- Prediction registered for v4 collection: none specific to the 34
  corridor (its riders dispersed two years before our collector existed).
  The durable ask this adds to the data request: **historical APC for
  cancelled routes**, so "low demand" cancellations can be audited at all.

## Sources

- Feed vintages: the project's frozen GTFS archive (Wayback Machine vintages; SHAs on file) (SHA-256s on file in the project archive manifest).
- City service-change announcement (mississauga.ca, Feb 5 2024):
  "Route 34 Credit Valley will be cancelled due to low customer demand.
  The resources from this cancellation will be reinvested in Route 35…"
- Transit Toronto, "MiWay revises routes and services, February 26"
  (2024-02-22): cancellation and 9 Rathburn-Thomas revisions.
- mississaugatransithistory.ca route listing (snapshot 2026-05-26 vintage
  data): 34 Credit Valley active dates.
- Stop-substitution and reinvestment numbers: computed from the vintages
  above; reproducible with the vintage-trip-count method used throughout
  this directory (weekday-normalized Wednesday counts).
