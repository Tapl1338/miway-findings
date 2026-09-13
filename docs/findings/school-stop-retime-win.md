# The September 7 retime worked where it mattered most — school stops

> **Version:** 1 (2026-09-12) · **Data:** recorded-departure feed
> (`obs_lateness`), dated rows 2026-08-23 → 2026-09-11, weekdays only ·
> **Eras:** pre = Aug 23–Sep 5 (old schedule, schools out of session),
> school = Sep 8–11 (new schedule, schools in session) · **Method and
> per-level definitions:** trip-level school service flags derived from
> the GTFS timetable (a trip counts as *school-serving* when it stops at a
> school's own transit stop during a bell-time wave window; see the
> companion school-wave work, details on file). Full receipt with CSVs:
> private repo `docs/runs/school-era-control-receipt-20260912.md` (SHA on
> file).

## The finding in one line

The route network-wide got better after the September 7 schedule change —
but at school-door stops the improvement was **2.5× larger** than the
network control, and the worst early-departure group in the entire dataset
(school trips before the change, **62% departing >2 minutes early**) was
pulled to near the network norm.

## The numbers

Early-departure share = recorded departures more than 2 minutes ahead of
schedule (the definition used across this project's reports; an early bus
is a missed bus for a rider who arrived on time).

| Group | Pre (Aug 23–Sep 5) | School era (Sep 8–11) | Change |
|---|---|---|---|
| **School-door stops** | **62.3% early** (n=970) | **38.9% early** (n=496) | **−23.4 pp** |
| Stops near schools (≤800 m) | 39.2% (n=16,651) | 24.5% (n=7,502) | −14.7 pp |
| Everything else (control) | 35.6% (n=327,639) | 26.0% (n=138,803) | −9.5 pp |
| Mean lateness, school stops | −2.84 min | −0.27 min | +2.57 min |

## Why this matters

1. **The headline improvement is real, not composition.** The control
   group — trips with no school connection — improved 9.5 points on its
   own, so the network-wide early-departure drop across the changeover is
   not an artifact of the service mix shifting toward school trips. The
   school-stop improvement comes *on top of* a genuine network effect.
2. **The pre-change failure mode was extreme and targeted.** Before
   September 7, a trip serving a school stop departed >2 minutes early
   62% of the time — nearly twice the network rate. For a student, an
   early departure is the worst failure direction: the bus is gone, and
   the next one may be a full headway away (or, at a 31-minute hole, half
   an hour).
3. **MiWay's own bell-alignment program demonstrably moved its metric.**
   The September 7 notice re-timed school trips "to align with new bell
   times" at eight-plus schools. Whatever else the change did, at the
   stops where timing failure costs students the most, the retime worked.

## Honest caveats

- The school era is only 4 weekdays — these cells will be rescored at the
  pre-registered September 22 checkpoint with ~10 school days.
- The eras differ in schedule, demand, and season simultaneously; this is
  a like-for-like *split*, not a causal isolation. (The control group's
  9.5-point move is itself part of that shared cause bundle.)
- School-door cells are small (970/496 rows across ~15 named school
  stops); treated as a targeted signal, not a precise rate.
- Occupancy sensors cannot see loads below ~13 passengers (documented
  elsewhere in this repo), which is why this finding uses departure-time
  records, not load data.

## Provenance

- Departure records: collector feed archive, 2026-08-23 → 2026-09-11
  (dated rows only; 3.48M recorded-departure rows total, of which 484,257
  fall in the two eras on weekdays).
- School service classification: weekday trips across both schedule
  vintages in the feed (26AU03 + 26SE07), matched to school-door stops by
  scheduled time (±1 min).
- Canonical thresholds: early = `lateness < −2 min`; recorded = actual
  (not forecast) departures. Identical definitions pre and post.
