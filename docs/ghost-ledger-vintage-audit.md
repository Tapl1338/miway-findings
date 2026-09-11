# Appendix — Ghost-ledger vintage audit (2026-09-11)

**Why this page exists:** while pre-scoring the September 7 pre-registered
predictions, the live ghost-ledger reported an August ghost rate of
~0.2–0.9% — where the published, frozen August cut says **3.08%** for the
same service dates. A number that looks *better* than the evidence that made
it famous is exactly the kind of number this project audits. What follows is
the day-by-day forensic: what broke, which days to trust, and what changed.

This is the project's third published data-integrity catch (after the
1-in-32 → 1-in-60 ghost correction and the silent Syncthing sync stall). It
is published deliberately: **early errors, kept honestly, are the strongest
evidence that a measurement pipeline is trustworthy.**

---

## TL;DR

| Question | Answer |
|---|---|
| Was the 0.36% ghost rate real? | **No — measurement artifact.** Do not quote it. |
| What is the trustworthy current-generation ghost rate? | **0.59% weekdays / 0.74% overall**, computed over 11 days with complete snapshot coverage (Aug 23, Aug 30 – Sept 8). |
| Did the Sept 7 schedule change reduce ghosts? | **Unknown / pending.** The pre- and post-change detector generations are not comparable. The frozen post-change cut (being collected now) will answer it. |
| Did any published finding break? | **No.** The early-departure / punctuality findings come from `obs_lateness.csv`, which passed every integrity probe and is unaffected. |
| What was fixed the same day? | The ledger's ownership gap: the daily analysis task now upserts the ledger (`--ledger`), fresh Sept 9–11 rows are born clean, and the Sept 9 broken row self-repaired on recompute. |

---

## What happened (the mechanism, three layers)

1. **The detector recomputes from whatever snapshots survive rotation.**
   Raw `vp_*.json` files are pruned after ~10 weeks. Any recompute for a
   date whose snapshots were pruned re-classifies those trips as
   *uncovered* — and uncovered trips can't be ghosts. Rates mechanically
   collapse.
2. **A Sept 9 one-shot backfill rebuilt the whole ledger from the
   then-surviving snapshot set** and stamped all 24 rows with a single
   timestamp. Early-August rows (partially rotated) came out 27–72%
   "uncovered" with structurally deflated ghost counts.
3. **The detector itself evolved** (verify-tail 5→15 min, a 20-minute
   start-grace, a post-midnight matching fix). Same dates, three
   generations, three different answers: frozen pre-fix 3.08% → corrected
   generation 1.59% → backfill ~0.5%.

The tell that made it auditable: **every ledger row carried the identical
`last_run` timestamp** — a monoculture no live process could produce.

## Per-day reliability (the gauge: % of scheduled trips "uncovered")

Low uncovered = the row was computed over complete snapshot coverage, i.e.
it measures what it claims. High uncovered = recomputed over pruned/partial
snapshots = ghost counts structurally undercounted.

| Tier | Service dates | Uncovered % | Verdict |
|---|---|---|---|
| **A — reliable** | Aug 23, Aug 30 – Sept 8 (11 days) | 0–3% | current-generation numbers; comparable to each other |
| **B — mostly OK** | Aug 24–28 | 4–10% | usable with caveat |
| **C — suspect** | Aug 20–21, Aug 29 | 12–22% | recomputed over partial snapshots |
| **D — garbage** | Aug 17–19, Aug 22 | 27–72% | ignore (rotated-away snapshots) |

**Reliable aggregate (Tier A): 45,821 verifiable trips, 341 ghosts =
0.74% overall; weekdays only: 0.59%.**

Two subtleties the per-day audit surfaced:

- **Sept 8** (cutover day, collected by laptop until evening and VPS after)
  shows a *complete* day: real, but **unreproducible** — 10 of ~850 of that
  day's snapshots survive on disk. A data-governance flag, not an integrity one.
- **Sept 9** initially sat in the garbage tier (1,449 uncovered) because the
  backfill ran before that day's late-evening snapshots existed on the
  laptop. The same day's recompute **self-repaired** (5,564 verifiable,
  0 uncovered) once coverage completed — the audit's tiering logic
  predicted its own resolution.

## What this is NOT

- **Not a data loss.** The raw corpus (`obs_lateness.csv`, 4.2M rows) passed
  structural probes: zero malformed fields in 4.2M, no sentinel clipping,
  no precision drift between eras, honest tails (lateness −63.8 → +258.4),
  and the exact-0.0 pile (0.74%) is the genuine early↔late crossing density,
  not a default value.
- **Not a schedule-change effect.** The confusion is detector-generation,
  not bus behavior.
- **Not silent.** The flag was raised by auditing a number that looked too
  good, the same way the 1-in-32 error was caught. The repo records the
  miss in the commit that tried to prevent it (`db5dce1` fixed the *next*
  failure mode and documented the previous one in its own message).

## The fix (landed 2026-09-11)

- The **daily analysis task is now the ledger's sole writer** (`--ledger`
  upsert per run; rows for un-recomputed dates are preserved byte-stable).
- Provenance is a first-class field going forward: **never delete bad rows —
  stamp them** (`computed_at` / `source` columns; each row's truth = the
  coverage at its write time).
- The post-changeover evaluation (Sept 22 scorecard) scores ghosts against
  the **frozen post-cut vintage only**, never against blended history.

## Standing lesson

Every failure in this project's short life has been the same species:
**a number that looked fine because the thing checking it had quietly
stopped checking.** The countermeasure is not vigilance — it's structure:
single-owner writers for every derived file, provenance stamps on every
row, and standing checks that flag constant timestamps, frozen counters,
and too-clean distributions as *findings* rather than features.
