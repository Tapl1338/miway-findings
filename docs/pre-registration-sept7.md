# Pre-Registration: Sept-7 Schedule Change Predictions

**Committed:** 2026-08-24 (before first post-Sept-7 capture)  
**Author:** alpha-8 (INNOVATOR seat)  
**Status:** PRE-REGISTRATION — NEEDS-VERIFY by non-author handle  
**Purpose:** Falsifiable predictions for the Sept-7 MiWay service change, committed before data arrives. Per measurement plan #2 and TASKS.md T20.

---

## Basis Artifacts (Frozen Pre-Change Baselines)

| Artifact | Commit / Path | Key Baseline Values |
|---|---|---|
| GTFS pre-change | `docs/sources/gtfs_archive/miway_gtfs_2026-08-23_pre-sept7.zip` (SHA `f43fb0a9de891dbd`) | 67 routes, current schedule |
| exec-summary.json | `docs/exec-summary.json` (unified-120 run) | `saved_pax_minutes`: 9,737.7; `base_avg_wait`: 18.82 min; `opt_avg_wait`: 17.08 min |
| equity-report.json | `docs/equity-report.json` (unified-120 run) | `passenger_minutes_saved`: 9,737.6; Ward 9: 21 stops, +2.56 min avg, 15 worse-off |
| T03 harness | `backend/scripts/sept7_compare.py` + `docs/runs/T03-dry-run.md` | Meadowvale Terminal: all deltas 0.000 on identical feeds |
| Collector window (feed-side) | `obs_lateness.csv` through 2026-08-23 | 7-day window: 602/20,948 ghost trips (2.9%); 30.7% >2 min early (n=352,077) |
| Ridership dataset | `app/data/ridership.csv` (Oct 2024 board period) | 10 real routes, 47 estimated |

---

## Predictions

### 1. Transfer Analysis Re-Run (New vs Old GTFS)
*Identical-model comparison per measurement plan #2: `equity_report.py` + transfer analysis on both feeds with `--period all_day --volume-mode ridership --max-connections 6000 --ward-csv app/data/ward_stops.csv`.*

| Metric | Current (Pre-Change) | Predicted Post-Change | Direction | Rationale |
|---|---|---|---|---|
| **Network `saved_pax_minutes`** | 9,737.7 (exec-summary) / 9,737.6 (equity) | **9,500–10,000** | ↔ Slight ↑ or ↔ | MiWay announcement targets Routes 8/66 connections; our model already finds 6,000 connections. Frequency improvements on announced routes should create modest new savings, but capped at 6,000 connections and 5-min shift limit. |
| **Network `base_avg_wait`** | 18.82 min | **18.5–19.0 min** | ↔ ~flat | Schedule shifts on 2 of 67 routes unlikely to move network average >0.3 min. |
| **Ward 9 `delta_minutes` (avg)** | +2.56 min (worse) | **+1.5 to +3.5 min** | ↔ Within noise | Ward 9 stops include Meadowvale pairings (109/10/313/43) and Route 43 corridor. Frequency gain on 43/109 may help, but offset optimization can shift waits both ways. |
| **Ward 9 `worse_off_stops`** | 15 of 21 | **13–17** | ↔ Stable | Live-weight drift (T01) already causes 15↔9 wobble between runs. Sept-7 change is smaller than live-weight drift magnitude. |
| **Route 8 connections** | Not separately tracked | **Improvement on announced pairs** | ↓ Waits | MiWay announcement explicitly targets Route 8 connections. Our model should show reduced realized waits for 8↔X pairs where frequency increases. |
| **Route 66 connections** | Not separately tracked | **Improvement on announced pairs** | ↓ Waits | Same as Route 8 — announcement targets 66 connections. |

### 2. Meadowvale Town Centre Terminal (T03 Harness — Realized Waits)
*Identical lateness pool, buffer 2 min, horizon 60 min, 300 iterations, seed 20260907. Current dry-run: all 0.000 deltas on identical feeds.*

| Route Pair (from→to) | Current `realized_mean_min` | Predicted `realized_delta_min` (new−old) | Direction | Rationale |
|---|---|---|---|---|
| **43 → 109** (acceleration transfer, plan #23) | 1.96 min | **−0.5 to −1.5 min** | ↓ Improves | Route 43 frequency increase (announced) directly shortens wait for 43→109N acceleration riders observed Aug 18–21. |
| **109 → 43** | 18.65 min | **−1.0 to −3.0 min** | ↓ Improves | 109 is Meadowvale Express; frequency boost on 43 reduces reverse-direction wait. |
| **10 → 43** | 18.25 min | **−0.5 to −2.0 min** | ↓ Improves | Route 10 feeds 43; 43 frequency gain helps. |
| **45 → 109** (acceleration) | 5.25 min | **−0.5 to −1.5 min** | ↓ Improves | 45→109N acceleration pair benefits from 109 frequency if increased. |
| **313 → 43** | 29.55 min (high missed: 0.952) | **−2.0 to −5.0 min** | ↓ Improves | High missed share → frequency increase on 43 has outsized impact on tail waits. |
| **38 → 43** | 18.09 min | **−0.5 to −2.0 min** | ↓ Improves | 38 is a trunk route; 43 frequency gain helps cross-transfer. |
| **All other pairs at Meadowvale** | Various | **−0.5 to +0.5 min** | ↔ Flat | Routes not in announcement unlikely to see schedule shifts large enough to move realized waits beyond noise floor (~0.5 min). |

> **Missed-share prediction:** Pairs currently with `realized_missed_share > 0.5` (e.g., 10↔313 at 0.94, 38↔313 at 0.95, 43↔313 at 0.55–0.62) should see **missed-share reductions of 0.05–0.15** if the Sept-7 frequency increases on Routes 43/109 materialize as announced.

### 3. Collector Feed-Side Metrics (Continued Collection Across Change)
*Per measurement plan #3: collector continues running; pre/post comparison of observed lateness, crowding, ghosts. Predictions are directional — exact values depend on ridership response.*

| Metric | Current (7-day window to 2026-08-23) | Predicted Post-Change (Sept 8–14 window) | Direction | Rationale |
|---|---|---|---|---|
| **Ghost trip rate** (trips never appearing in RT feed) | 602 / 20,948 = **2.87%** | **2.5–3.5%** | ↔ Stable | Ghosts reflect dispatch/ops reliability, not schedule. Sept-7 is a timetable change; no ops overhaul announced. |
| **Early departure rate** (>2 min early) | **30.7%** (n=352,077) | **29–33%** | ↔ Stable | Early departures driven by recovery-time depletion in traffic; schedule padding changes on 2 routes won't move network rate >2 pts. |
| **AM peak early rate** (07:00–09:00) | **37%** (n=30,900) | **35–39%** | ↔ Stable | Same rationale; peak congestion unchanged. |
| **Night crowding (Route 109 PM rush)** | 40% avg, 22.2% SRO (n=19,854) | **38–42% avg, 20–24% SRO** | ↔ Flat to slight ↓ | If 109 frequency increases as announced, peak loads spread across more trips → modest crowding relief. |
| **Night crowding (Route 2 midnight)** | 42% avg, 21.0% SRO (n=11,093) | **40–44% avg** | ↔ Flat | Route 2 not in announcement; no frequency change expected. |
| **Routes ≥33% full after 19:00** | 6 routes (31, 61, 2, 110, 66) | **5–7 routes** | ↔ Stable | Route 66 may drop off if frequency increases; Route 31/61/2/110 unchanged. |

### 4. Specific "Guardrail" Predictions (Plan #23)
*Per measurement plan #23: track acceleration transfers (e.g., 45→109N) and local→express pairs that could silently break under re-timing.*

| Prediction | Test |
|---|---|
| **45→109N acceleration transfer preserved** | Realized wait for 45→109 at Meadowvale does not increase >1 min; connection remains in optimized solution. |
| **No Meadowvale pair degrades >2 min** | Max `realized_delta_min` across all Meadowvale pairs ≤ +2.0 min. |
| **Route 8/66 announced connections improve** | At least 3 of top-5 Route 8 or 66 pairs at Meadowvale show `realized_delta_min < −0.5 min`. |

---

## Falsification Criteria

This pre-registration is **falsified** if ANY of the following occur in the post-Sept-7 data (first capture window Sept 8–14):

1. **Network `saved_pax_minutes` falls outside 9,000–10,500** (i.e., >10% shift from baseline) — indicates model instability, not schedule effect.
2. **Ward 9 `worse_off_stops` > 18 or < 10** — exceeds live-weight drift envelope (T01: 9↔15 observed).
3. **43→109 realized wait increases** (delta > 0) — contradicts announced frequency increase on Route 43.
4. **Ghost rate > 5% or < 1.5%** — implies collector artifact or ops change beyond schedule.
5. **Early departure rate shifts > 4 pts** (outside 27–35%) — implies non-schedule factor.
6. **Any Meadowvale pair with missed_share > 0.5 sees missed_share INCREASE** — contradicts frequency-increase expectation.

---

## Verification Protocol

1. **After first post-Sept-7 capture (T10):** Run `sept7_compare.py` with `--old-zip` = pre-sept7 baseline, `--new-zip` = post-sept7 capture.
2. **Re-run equity_report.py** on new feed with identical args; compare against this table.
3. **Collector window Sept 8–14:** Compute feed-side metrics from `obs_lateness.csv` and `occupancy_stats.csv`; compare against Section 3.
4. **Non-author handle verifies** (NEEDS-VERIFY): A different handle re-runs the comparisons independently and posts a STATUS row `verified` or `verified-for-send` with `artifact:line` evidence.
5. **Falsifier (alpha-6) may attack** before referee co-signs.

---

## Notes

- Predictions are **directional and banded**, not point estimates. The noise floor from live-weight drift (T01: ~17% equity-report spread across data vintages) and solver stochasticity (~0.09% on identical params) sets the minimum detectable signal.
- The T05 bundle (same_terminal_walk ON + bay-walk floor) activates **inside the post-Sept-7 window** per DEC-01 deferral. This pre-registration assumes CURRENT basis (flag OFF); if T05 runs concurrently, a second pre-registration for the new basis would be needed.
- Route 43/109 frequency change magnitude is not yet quantified in the public announcement. Predictions assume modest headway reduction (e.g., 15→12 min or 20→15 min). If MiWay adds trips, effects scale up.
- "Night crowding" predictions assume ridership doesn't surge in response to frequency (induced demand on weekly timescale is negligible).