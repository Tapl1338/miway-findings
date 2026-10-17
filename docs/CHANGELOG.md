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

## Week of Oct 12–18, 2026

### Added
- **Claim-verified GTFS tools for coding agents** — an MCP server exposing
  the project's three verification commands (claim check, departures at a
  stop, trip plan) so an agent answers from the instrument instead of from
  memory; thin wrappers over the same parsing rules the analyses use.
- **Two more CI gates** — a design-token ratchet (every UI colour answers to
  a token or a per-file baseline that can only shrink) and a rider
  happy-path end-to-end run against the static build.
- **Two-city window integrity check** — diffs consecutive day-stat counters
  and cross-checks the observation file's own date column, because the
  day-stats file cannot tell a complete day from a partial one.
- **TTC observation retention** — a weekly job whose installer refuses to
  arm unless the running collector provably started from lock-bearing code;
  the prune under it classifies rows without holding the lock and takes the
  lock only to commit.

### Changed
- **Explicit feed-era labels on the standing GTFS capture** — the wrapper
  used to inherit the previous era's default, so a capture spanning a
  changeover could be filed under the old one. It now passes its own id, and
  a test fails if that id goes missing.
- **Published floors moved to 9M+ departures / 130,000+ polls** (live
  9,008,463 and 130,146), with the previous figures added to the retired list
  so a copy-paste from an older variant fails the gate instead of quietly
  re-publishing a number weeks behind the instrument.

### Fixed
- **The day-counter trap** — one in-memory stats dict was re-labelled at
  midnight without resetting, so each day file held a running total since
  process start (a day that polled 690 times read 8,738). Day files now
  reset at the calendar boundary and declare their scope; readers difference
  legacy files and report a restart day as the lower bound it is.
- **Dashboard memory** — the in-process memo was unbounded (215 MB to
  1,328 MB across ten endpoints); it is now an LRU sized by the on-disk
  pickle, and a healthy-but-huge API worker is recycled rather than trusted.
- **Analysis chain memory** — the peak report read an 8.9M-row file into a
  list of dicts (5,780 MB peak); streaming it is 914 MB with byte-identical
  output, and an explicitly empty window is a no-op rather than a failure.
- **The post-window cutover is one dated command** — it ships the staged
  bundle hash-compared, restarts the collector only if the running code
  predates the ship, proves the restart from systemd facts plus a fresh
  heartbeat, then arms retention; a dry run ships, restarts and arms nothing.

## Week of Oct 5–11, 2026

### Added
- **Findings snapshot v7** (Sept 28 – Oct 4) frozen and promoted — the
  cleanest collection week since the September change, with all seven days
  datable after a backfill for two battery-skipped days.
- **Pre-registration for the October 26 change** — prediction bands filed
  ahead of the change, with a non-author verifier and the basis baselines
  receipted.
- **Box-check workflow** — read-only, dispatchable probes for both collector
  boxes, because the environment blocks SSH and ICMP and every prior
  diagnosis stalled on access.
- **Feed-size comparison** — weekly trip counts re-derived per date for both
  networks (249,592 vs 34,092, a 7.32x difference) after two earlier figures
  were traced to a calendar_dates omission rather than the feed.

### Fixed
- **CI lint** — 42 ruff violations and 24 unformatted files cleared, plus
  two failures the red lint job had been masking; the fixes had been sitting
  uncommitted while the remote stayed red.
- **Feed-vintage-brittle tests** — nine backend tests pinned expectations to
  the live feed; they now derive them at run time or pin the contemporaneous
  archived feed, so a timetable roll stops breaking the suite.
- **A same-day wording reversal** — an awards line was swept across the live
  documents and restored by the owner hours later; the rendered PDF had
  missed the sweep, and the tracked file now matches the decision.

## Week of Sept 28 – Oct 4, 2026

### Added
- **Second collector for Toronto's TTC** — cadence gates passed, giving a
  second network on which to test whether the method generalizes; its
  calendar-filtered index was rebuilt at a third of the size.
- **Rider-shaped home** — one surface for what is wrong right now, a
  favourites store and a trends strip, replacing the 19-view surface frozen
  as tag `v1.0`.
- **Referee verification page** — every headline number on one page with the
  command that re-derives it, generated from the claim registry rather than
  written by hand.
- **Public test tree** — a scrubbed copy of 157 of 160 test modules published
  so the claims can be audited instead of trusted, with a leak-guard and
  promotion gate around the copy.

### Changed
- **Collector dedup bounded to a watermark** instead of rewriting the whole
  corpus each cycle, so memory tracks the window and not the file.

### Fixed
- **Collector memory, root-caused** — the growth was allocator arena
  retention rather than the kernel, proven by a probe on a scratch process;
  a threshold-triggered guard now restarts the unit before it wedges the box
  instead of letting the kernel pick a victim.
- **TTC unmatched metric** corrected after an audit found the denominator
  counted entities that could not be measured.
- **CI revived** after a week dark, with three gates repaired.

## Week of Sept 21–27, 2026

### Added
- **v1.1 five-view consolidation** — Home, Map, Plan, Measure and Trust
  replace the 19-view surface, built to a pre-registered spec, with URL
  routing and deep links that survive a reload.
- **Mobile 390 px regression gate** — a scripted audit that replays the
  manual swipe through all 16 sections on every push, plus the map-sliver,
  header, tap-target and table-wrapper fixes it found.
- **Uptime SLO report** — availability defined as full-day coverage with a
  monthly receipt, so the reliability claim has a number behind it.
- **Installable frontend** — PWA manifest, offline shell, share metadata and
  reduced-motion support.

### Changed
- **Demo fetch layer is live-API-first** — pages probe the evening read-only
  API and fall back to frozen snapshots per visit, same interface either way.
- **Route-level code splitting** — every panel except Home is lazy-loaded.

### Fixed
- **Transfer and trip-check correctness** — terminal-only co-location
  phantoms no longer rank as missed transfers, a cross-direction stop
  sequence bug is fixed, and planner clock labels no longer imply a walk leg
  is a bus.
- **Collector crash-safety** — writes are atomic and lock-tolerant, and one
  malformed realtime poll no longer kills a whole collection window.

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

## Week of Oct 5 – Oct 11, 2026 (in progress)

## Week of Sept 28 – Oct 4, 2026

### Added
- **Published test suite** — 157 scrubbed test modules shipped for audit,
  with the reproducibility framing corrected to match (the public repo runs
  no CI, so the old "CI-enforced coverage floor" claim is gone).
- **Referee verification page** — every headline number on the site paired
  with the command that re-derives it ([verification](claim-verification.md));
  five more claims backed by published freeze artifacts, the
  [evidence-freeze manifest](evidence-freeze-manifest.md) published, and the
  page re-rendered against the 18-claim registry.
- **v7 findings snapshot frozen** (Sept 28 – Oct 4) — fourth post-change
  week: ghost rate 1 in 253 (89 of 22,492 verifiable trips), early
  departures 22.8%, AM peak 28.8% — the cleanest collection week since the
  change, all 7 days datable after the battery-skip backfill
  ([v7](findings/findings-v7-sept28-oct4.md)).

## Week of Sept 21–27, 2026

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
- **v6 findings snapshot frozen** (Sept 21–27) — third post-change week:
  ghost rate 1 in 235, early departures 22.1%, collected through the
  project's worst instrumentation week (a 23.5h cloud-box outage, then a
  stalled sync channel) with every caveat stamped pre-publication
  ([v6](findings/findings-v6-sept21-27.md)).

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
