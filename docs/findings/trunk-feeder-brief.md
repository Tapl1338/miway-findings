> **Promoted 2026-09-11 from the project's private analysis repo**
> (`docs/trunk-feeder-brief.md`; frozen as of its stated vintage — numbers are reproducible
> via the scripts named inside, run against the collection described in the
> [data dictionary](../../data/README.md)). Published as-found: early errors
> are kept honestly per the [vintage audit](../ghost-ledger-vintage-audit.md).

# Mississauga's most winding bus routes, fixed at zero cost

**One line:** 36 of MiWay's meandering routes — carrying about **80,000 riders a day** — can be rebuilt as a direct "trunk" plus a local "feeder" that keeps every current stop: same buses, same drivers, same budget, and roughly **170 km less route distance run every day**.

## The story in one route: the 10 (Bristol)

Route 10 carries **~4,000 riders a day** along a corridor it travels at 2.26× the distance needed — **20.6 km to go 9.1 km** as the crow flies, with a long loop off the main line. And those aren't empty buses: each of the 10's **202 weekday runs carries ~20 riders** — double the network median (10.1 riders/bus).

The proposal splits it:

- **Trunk 10:** Meadowvale Town Centre → City Centre Transit Terminal — the direct line, **16.5 km**, borrowing Route 66's alignment. Route 66 isn't just any corridor: it is the **single most productive route in the network (43.4 riders per revenue-hour vs the 18.0 average)** — the direct line the 10 needs demonstrably already exists and already carries riders.
- **Feeder 10A:** takes over the Bristol Rd loop (Bristol Rd At Fairwind Dr → City Centre) — every stop the 10 serves today still gets a bus.

Riders going end-to-end see their trip cut by roughly 4 km. Riders on the loop keep their stop — they transfer where the trunk and feeder meet.

**Route 39 (Britannia), 4,459 riders/day, is the same idea:** today it runs 27.7 km (1.72×), including a detour down Lisgar Dr. The trunk borrows Route 48's direct routing down the corridor (21.8 km, 1.35×), and a feeder keeps the Britannia Rd section served.

## What's proposed network-wide

| | |
|---|---|
| Routes redesigned | **36** (9 borrow an existing route's corridor; 27 get a brand-new direct line over streets buses already drive) |
| Riders on those routes | **~80,500 weekday boardings** |
| Route distance cut | **625 km → 456 km** of trunk (about **170 km less** per day) |
| Circuity improvement | The worst offenders drop sharply: 10: 2.26× → 1.81× · 38: 2.40× → 1.85× · 39: 1.72× → 1.35× |
| Stops lost | **None** — feeders cover every dropped span |
| New buses / drivers | **None** — the same fleet serves shorter, faster lines |

Every proposed line follows a street some MiWay route already drives today. Trunk and feeder meet at real stops, so transfers are where buses can actually be.

## Why this works for riders and the city

- **Faster end-to-end trips on routes with real ridership** — 10, 39, 7 (5,900/day), 38, 110 are the standouts. These aren't empty buses: the winding routes carry **10–27 riders per bus** (network median 10.1), so shortening them speeds up full buses, not empty ones.
- **Better frequency for the same money** — a bus that spends 20 minutes less per loop can serve the line more often, or be redeployed.
- **No one is left behind** — the feeder keeps local coverage; the trunk makes the long haul fast.

## Start here: a schedule-only pilot (weeks, not months)

Before redesigning any route, there's a **zero-cost fix that staff can approve and run in weeks** — it moves no stops, changes no routes, adds no buses. It just **re-times existing buses** so transfers line up.

The busiest transfer hub in the network is **City Centre Transit Terminal** — **31,573 weekday connections across 16 routes**, more than double any other stop (Kipling is next at ~13,000), and it sits among the highest-friction stops (40.2/50 on the app's wait-based friction score). Today its riders sit through these waits that a schedule re-timing alone can remove:

| Connection | Wait today | Riders affected (est.) |
|---|---|---|
| 61 → 7 | 21 min | ~73/day |
| 2 → 7 | 18 min | ~72/day |
| 66 → 7 | 14 min | ~75/day |
| 66 → 10 | 15 min | ~31/day |
| 109 → 68 | 19 min | ~22/day |

Network-wide, re-phasing cuts the average transfer wait from **18.4 → 16.7 min** and removes roughly **430 missed connections per weekday** (~2,840 → ~2,410) — about **7,400 weighted wait-minutes saved per day**, at zero added cost.

**Measurement plan (the before is already measured):** the 2026-08 collection captured 2,317 recorded Route 10 departures — they ran a mean **0.8 min early**, with 66% of buses leaving *ahead* of schedule. So connections fail even when the schedule says they should work, and that is exactly what re-timing + on-time holding fixes. Midday Route 10 crowding measured 0.1% (2,073 observations) — buses have headroom, so re-timing is low-risk. A pilot would: (1) re-time the affected routes, (2) keep the GTFS-RT collector running through the pilot, (3) report waits, on-time performance, and boardings before/after from the same collection method.

**The ask:** have MiWay staff re-time the handful of routes serving City Centre so these transfers land within 12 minutes. No service change, no consultation needed, no new money — just a schedule edit and the same measurement we already run.

## The ask (Phase 2: the redesign)

Beyond re-timing, the bigger structural fix is the trunk + feeder redesign. A **6-month pilot** on one corridor — Route 10 is the natural candidate: high ridership, a donor corridor that already exists (66), and a clean before/after story. City staff would validate the GTFS-level plan against road conditions and signal timing; the pilot measures whether riders come back when the bus stops winding.

---

### Caveats (read this first)

- Proof-of-concept built from **public GTFS data** — a proposal tool, not an engineering study. Curbs, turn radii, and signal timing need staff review.
- **Cost savings are route-distance savings**, not dollars; the pitch is *same budget, better service*, not "money back."
- **The most winding route, the 36, is not the best headline.** It's a low-ridership local loop (~1,665/day) whose value is *local coverage*, not through travel — and riders crossing from Winston Churchill Station to South Common can already do so via the 109 into the 48/110, all relatively high-frequency routes. The 36's trunk+feeder keeps its local service intact and speeds the direct run, but the win there is smaller than the numbers on the other routes. The pilot should start where the ridership is: 10, 39, 7, 38.

---

### The cold email (150 words)

> **Subject: A free fix for Mississauga's bus transfer waits**
>
> Hi Councillor [Name],
>
> City Centre Transit Terminal is MiWay's busiest transfer hub, and riders there wait 14–21 minutes for connections the schedule could easily line up. I've built a tool that analyzes MiWay's full network and finds where re-timing existing buses — no route changes, no new buses — removes those waits at zero cost. It cuts the average transfer wait from 18.4 to 16.7 minutes and removes ~430 missed connections a weekday.
>
> The same tool also proposes route redesigns: Route 10 (Bristol) travels 20.6 km to go 9.1 km — a direct trunk plus a feeder keeps every stop and saves ~4 km per run, with 35 more proposals covering ~80,000 weekday boardings.
>
> Could I get 15 minutes to walk you through the map? Or, if transit isn't your portfolio, would you forward this to MiWay staff?
>
> [Name] — [phone]

*Attach: this one-pager + a screenshot of the Trunk & feeder map (Route 10 before/after).*
