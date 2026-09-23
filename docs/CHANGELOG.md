# Changelog

Feature and engineering timeline for the MiWay Transit Optimizer project.
Findings (data results) live in the immutable [snapshots](findings/README.md);
this file records what was **built and changed**, week by week, drawn from the
two repos' git history (private monorepo `miway-transit-optimizer` + this
public showcase). Measured results are linked, never restated — each figure
has exactly one authoritative home.

Weeks are Mon–Sun. Newest first. Curated: PR/multi-agent chore rows are
collapsed into the user-visible change they produced.

---

## Week of Sept 14–20, 2026

### Added
- **Interactive public demo** — the full dashboard replaying frozen API
  snapshots on GitHub Pages, with a demo-vintage banner; optimiser replay
  runs the pre-computed CP-SAT result end-to-end ([demo](../demo/)).
- **Weekly pre-registrations** — falsifiable week-over-week predictions
  committed before the window's data; first stability-window registration
  covers Sept 14–20 ([sept14-20](pre-registration-sept14-20.md)).
- **Snapshots index + version tags** — v1–v4 each pinned to the commit that
  froze them (`git show findings-v4`); auto-tagging wired into the weekly
  refresh ([index](findings/README.md)).
- **Zero-minute CI** — self-hosted GitHub Actions split across two runners
  (laptop ARM64 for the heavy suite; Oracle VPS cgroup-capped at 340 MB for
  the stdlib doc gate) after hosted minutes ran out; gate immediately caught
  a silent API bug and OpenAPI drift.
- **Orchestrator economy doctrine** — metering model for multi-agent
  sessions; window-budget scheduling folded into the dispatch playbook.
- Demo QR codes in the councillor brief and resume PDFs (decode-verified).

### Changed
- Weekly demo refresh now fully automated (health gate → capture → stats →
  build → push-only-if-changed) on a scheduled task.
- Demo fetch layer now **live-API-first**: the pages probe the laptop's
  evening read-only API through the tunnel and use frozen snapshots when it
  sleeps — same UI, freshest available basis, decided per visit.

### Fixed
- Public-docs drift gate found 3 stale twins (topology missing the Sept-19
  incident doctrine; README headline; findings-v5 banner) — all re-synced,
  gate back to 0 drift across 30 docs.
- Evening fallback API served without CORS headers (config read at import
  after process start) — the one use-case the deploy exists for didn't work
  cross-origin; caught by audit, verified fixed.
- A1 capacity hunt was double-blind: out-of-capacity answers arrived wrapped
  in a case-sensitive InternalError the classifier missed, and the second
  rung was 429-throttled seconds after the first call — fixed (honest
  OutOfCapacity logging, 120 s inter-rung gap) and the Git-Bash flock
  lockout that silently disabled the laptop hunter for 15 h replaced with a
  portable PID-lock.

### Added (final days)
- **July miss-model in the optimizer** — a missed connection now costs
  `max(wait, 0) + headway` instead of billing negative standing time; the
  old model provably rewarded making some misses *worse*. New default;
  canonical headline re-derived and unchanged within 0.2% (9,714.6 vs
  9,737.7) — the old number was a basis mismatch, not drift.
- **Bus-to-train downstream check** — every optimiser result can flag
  shifted MiWay arrivals against real GO-train departure tables at all 10
  shared stations, staleness-stamped (all six Milton-line stations flag the
  midday service valley; Lakeshore stations sit at 9–12.5-min medians).
- **README headline gate** — the public-facing savings figure is
  machine-checked against a basis-stamped artifact on every push and a
  nightly regeneration; prose can no longer out-run its evidence.
- **Capacity-threshold fitter (prep)** — per-vehicle APC capacities fitted
  from ascent-only flip transitions; real-data run shows the honest blocker
  (13 usable flips across 17 vehicles) and a per-vehicle capacity scatter
  of 42.5–165 vs the nominal 65/110 constants.

### Added (late week)
- **Equity constraints in the solver** (P2.3) — per-ward caps on total
  weighted worsening as MILP constraints, with per-ward overrides and a
  constraint-status/tradeoff block on every result.
- **Planner-ready report** (P5.2) — one run → one handoff package (KPIs,
  route impact, equity table, offsets, checklist) as JSON/CSV.
- **"Will I make it?" rider check** (P5.5) — arriving on route A, will I
  catch route B? Answered from observed departures with explicit
  uncertainty, and "not enough data" instead of a guess for thin pairs.
  Live in the [demo](../demo/) sidebar.

---

## Week of Sept 21–27, 2026 (in progress)

### Added
- **v1.1 five-view demo consolidation** — the 19-view surface collapsed
  into 5 shells (Home, Map, Plan, Measure, Trust), every panel folded as a
  section with its evidence badge preserved; real URL paths, legacy
  `#view` links redirect. Live in the [demo](../demo/).
- **Forecast scoreboard goes FINAL** — every pre-registered prediction now
  carries its mechanical verdict (3 forecasts, 26 bands); Forecast 1
  scored from the Sept-22 scorecard receipt, misses published alongside
  hits ([track record](findings/forecast-track-record.md)).
- **Forecast 4 pre-registered** (Sept 28–Oct 4) — the first registration
  built from two frozen weeks of basis instead of one, committed before
  the window's data exists.
- **Home trends strip** — week-over-week measured metrics (early
  departures, ghost rate, volume) on the demo Home, complete weeks only.
- **Promotion-freshness gate** — nightly check flags any public doc whose
  private twin was regenerated after its last promotion, closing the
  twin-drift window the existing content gate can't see.

### Fixed
- Demo trip-check crash: any API failure 404'd the whole app in demo mode —
  inline "Check failed" alert + a canonical snapshot replay instead.
- Demo "Why so slow?" view 404'd (slowness endpoints never snapshotted).
- Demo base-path incident: ad-hoc rebuilds shipped root-absolute asset
  URLs, blanking Pages since the prior refresh — rebuilds must set
  `DEMO_BASE`; rule encoded in the refresh script.

### Measured
- **Sept-7 pre-registration FINAL verdict** — 11/10 required post-change
  weekdays collected; 4 FAIL (early-departure and AM-peak bands beaten in
  the improvement direction), 2 UNMEASURABLE (baseline tooling superseded
  mid-study, documented per-band), 1 fail-low. Verdicts and basis notes in
  the [scoreboard](../demo/).

---

## Week of Sept 7–13, 2026

### Added
- **Findings v4 frozen** with SHA-256 evidence manifest; promoted to the
  showcase under the drift gate (now covering 22 promoted docs).
- **Findings pre-registration for the late-October change** (freeze Oct 12)
  — template + first registration.
- **VPS collector cutover completed** (Sept 9): Oracle Always-Free runs
  collection; laptop free to sleep; nightly backup rotation, cloud-ownership
  guard against duplicate collectors, anti-idle keepalive.
- **Analysis staleness guard** — coverage router field + watchdog + CI tests
  so laptop analyses can't silently run on stale replicas.
- **Bunching tracker** wired into the daily analysis.
- **Methodology page** — how every published number is measured.

### Fixed
- Post-changeover rollup week restored; WoW refuses thin comparisons.
- Collector-status banner reading a dead local heartbeat after the cutover.
- Calendar-unfiltered GTFS joins inflating trip counts ~4× — canonical
  `trips_at_stop.py` tool, raw joins banned, lesson recorded (double
  correction published in-place).
- Self-heal for corrupt interleaved rows in `obs_lateness.csv`; zombie-epoch
  guard dropping predictions >90 min stale.
- Night-2 lateness diagnosed: zero-slack 21-min night timetable + evening
  wave carried by interlining.

### Multi-agent infrastructure
- Free-lane swarm pool measured and pinned (Kilo/BlockRun/OVH capacities);
  multi-provider proxy with per-member concurrency caps and scoreboard.
- Scout-staged task dossiers; all-patch builder rounds (2m15s task execution);
  prewarm junctions (zero npm-install per worktree).

---

## Week of Aug 31 – Sept 6, 2026

### Added
- **Findings v3 frozen** (last pre-change week) — last weekly snapshot
  before the Sept 7 service change.
- **School walkshed layer** — all 19 schools geocoded; isolation findings
  (five one-route schools, three unserved by school trips); Graydon
  confirmed as a closed-2018 GTFS fossil.
- **Ridership honesty brackets** — estimate mid/upper columns; blind-route
  ridership estimated from the measured peak floor; below-APC-resolution
  routes treated as unknown, not tiny; Lyu & Yan elasticity band derived.
- **U of T thesis (public MiWay APC 2024 data) acquired and documented** as
  an external validation anchor; data-ask drafted for MiWay.
- Ward transit demand (TTS 2022) wired into the equity view.
- GTFS feed-watch reporting the live service period/era.
- `STREET-CORRIDORS.md` — the rider's inverse map (street → routes).

### Fixed
- Solver LP strengthening for rush-hour certification; solver run-variance
  surfaced in the API and UI; xdist-flaky split-brain test fixed.
- Daily battery-health snapshot (collector wear made measurable).

---

## Week of Aug 24–30, 2026

### Added
- **Sept-7 pre-registration** (2026-08-24) — transfer-analysis and
  realized-wait predictions for the schedule change, committed before any
  post-change capture.
- **Pre-change GTFS archive** with SHA pinning for identical-model A/B.
- **T03 dry-run harness** for Meadowvale Terminal transfer comparisons.

### Fixed
- APC sensor quantization floor characterized in the field (Aug rides):
  sensor cannot distinguish 5 from 12 passengers, never reads below 20%
  — recalibration brackets for every load figure.
- Drift-gate disagreement resolved by independent re-run: two BREAKS in a
  prior PASS verdict; escalation-to-referee process recorded.

---

## Week of Aug 17–23, 2026

### Added
- **Full-week GTFS-RT collection** (Aug 17 onward): hardening, Modern
  Standby sleep-hold fix, coverage dedup — the week that made n=7 windows
  possible.
- **Councillor package v1** (Aug 19–22): ward briefs, ridership validation,
  AM-peak early stat, Route 2 recovery observation, APC vignettes; frozen
  pre-send snapshot; presented to the Ward 9 Councillor's office (referred
  to MiWay staff — ongoing).
- **Multi-agent governance** — agent board protocol, referee escalation,
  audit-the-auditor checks, board self-check tooling.
- Late-night period presets, ride-on alternatives, direction-aware
  ridership views in the dashboard.

### Fixed
- Ghost-trip counting bug (post-midnight double-count): 1-in-32 corrected
  to 1-in-60, correction published in place in v1.
- GTFS export no-op optimization crash; late-night period wrap; equity map
  init; minutes-as-hours label.

---

## Week of Aug 10–16, 2026

### Added
- Project starts: MiWay GTFS + real-time ingestion, optimiser core
  (CP-SAT), analysis backend, dashboard frontend.
- First councillor-email draft and measurement plan.
