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

## Week of Oct 26 – Nov 1, 2026

### Added
- **The weekly findings freeze runs itself, and the reliability denominators
  behind October were repaired** — three windows had gone unfrozen (Oct 5–11,
  Oct 12–18, Oct 19–25) and nothing could have noticed: every nightly check
  looked at collector health, document quotes and promotion drift, and none
  looked at whether a snapshot had been produced. A staleness check now answers
  from the calendar and the snapshot table — a hole behind a current week fails
  too — and a Monday-morning task works out its own window and label, so a
  missed week is a failed check instead of a silent gap. It drafts nothing:
  step one of the weekly procedure is analysis. Snapshots
  [v8](findings/findings-v8-oct5-11.md),
  [v9](findings/findings-v9-oct12-18.md) and
  [v10](findings/findings-v10-oct19-25.md) came out of one shared cut, each
  pinned with its tag, and the reliability repair carries its own
  [erratum](findings/erratum-2026-10-26-reliability-denominator.md).
- **The TTC collector's static index stopped being 395 MiB of dictionaries** —
  two bind structures held 394.9 MiB of dicts to serve lookups that need
  integers. The compact rep is 37.9 MiB of columns, serialized per GTFS vintage
  and memory-mapped back in 0.13–0.16 s, so a restart inside a service day no
  longer pays a ~30 s rebuild. It shipped behind a shadow audit that re-binds
  every entity through both reps on every poll and classifies each divergence
  (`dict_only` / `compact_only` / `diff_tid` / `stopped_diff`), plus an offline
  row-and-order diff, because candidate order is part of bind semantics.
  Measured on the collector box after the flip: `MemoryCurrent` 528 → 201.9 MB,
  host swap 818 → 197 MB, `polls_failed` unchanged, `NRestarts` 0 — the flip
  runbook's three checks, with rollback one line deleted from the env file. The
  first version was 14x *slower* than the dicts it replaced, because a
  scalar-needle `searchsorted` linear-scans a 1.18M-element array; a
  precomputed extent table brings it to parity (829 vs 833 µs/entity).
- **The observation archive's history is frozen, so dedup stops rewriting it** —
  the watermarked dedup bought 290 → 241 s and no more, because most of that
  pass was copying a prefix the run could not change. Observations now live as
  immutable `obs/seg-YYYYMMDD-YYYYMMDD-<rows>.csv` segments plus one
  `obs/active.csv` holding only open service dates; a seal is a variant of the
  dedup rather than an extra pass — the same read, split into a segment write
  and an active write, with the segment fsynced before the active file is
  replaced so a crash there duplicates rows but never loses one. The 160 MB
  active cap now *bounds* a failure mode that was unbounded: a 24 h gap used to
  widen the pass to the whole corpus, which on this box is an OOM. A one-time
  migration dedups, partitions by date, proves per-date equality, and refuses a
  second run instead of doubling every row.
- **Skipped-stop announcements are persisted** — one line per (trip, stop) per
  Toronto service day, carrying the bound static pattern as context, because
  the feed re-announces a skipped stop on every poll while the trip approaches
  it, and because a dropped stop has to be distinguishable from a trip that
  never ran.

### Changed
- **Every TTC reader goes through the store, and a test keeps it that way** —
  the derive reads the week it needs (~8 segments) instead of all 26 M rows;
  the window check answers a per-date count from segment metadata plus the live
  tail instead of streaming ~700 MB; the prune expires whole segments; the
  backup archives `obs/` *with its path*, since a flattened copy would restore
  a corpus the store cannot see; and the guard fails any line under
  `backend/app` or `backend/scripts` that names the retired file and the TTC
  tree together. Two rows of the design turned out to read the MiWay corpus,
  not TTC's, and were recorded as corrections rather than "migrated" into a
  regression.
- **The poll loop keeps its configured period** — it slept the interval *after*
  each poll returned, so a 30 s setting with a 9.6 s median poll produced a
  42 s cadence that no speed-up could reach. Scheduling against the cycle start
  brought box 2 to 28–35 s gaps (~31 s mean), 129 polls/hour against 86, poll
  median unchanged.
- **Dedup copies the frozen head instead of re-parsing it** — the state file
  now carries `head_bytes`, the offset where the closed-date prefix ends, and a
  boundary that is not a newline (or is past EOF) discards the watermark and
  rescans. Measured on the live 1.65 GB file: 290.4 → 241.0 s. That is 1.2x and
  not the 10x the laptop fixture implied — parsing was only 49 s of the pass;
  the rest is a 3.2 GB rewrite on a disk measured at 37 MB/s, an ~80 s floor
  with no parsing at all. The measurement is the finding: the shape had to
  change, not the parse.

### Fixed
- **A partial-day pass could freeze a whole date at ~7% of its schedule** —
  the ghost ledger's `--since` cutoff made one sliver pass permanent, and the
  October snapshots inherited it; a full recompute over the same day verifies
  more trips than were stored, so the stored rows were the defect. Rows are now
  replaced only by a recompute that verifies at least the stored base, decided
  per date (a per-route rule let small-base routes through and still moved the
  day). The report is built from the merged rows rather than the run's fresh
  ones, so the CSV and the .md stopped disagreeing, and every October date was
  re-measured with a neighbour day on each side — a poll after midnight carries
  the previous service date, and one date alone undercounts by ~4%.
- **The freeze gate was unsatisfiable by construction** — it required a log
  line `rc=0 failed=0/8`, but the chain's last step exits 1 or 2 *by design* as
  an advisory, so every run since Oct 5 logged `rc=2 failed=0/8` and no window
  could freeze. The gate now tests the chain's own success definition. A
  mistyped PowerShell format string that threw *after* a successful freeze is
  fixed in the same script — the script had been reporting failure on success.
- **Compact-only mode silently rebuilt the dictionaries it was meant to
  replace** — the collector called an inner closure whose non-shadow branch
  went straight to the dict builder, so the cache directory stayed empty and
  the 395 MiB rep was rebuilt on every start while the suite stayed green: the
  wiring test exercised the helper the closure bypassed. A source-level test
  now pins the delegation and the one surviving direct build.
- **The retention job could never have run** — the unit set the data directory
  but not `PYTHONPATH`, and the prune resolves its imports from there by
  design, so the weekly job would have died with `ModuleNotFoundError` every
  Sunday. The journal had the same shape from the other side: Python
  block-buffers stdout under systemd, so startup lines appeared 42 minutes
  after they were stamped, which is what made a healthy collector look dead
  after every restart.
- **Three frozen snapshots still told readers not to quote their reliability
  figure**, and the only notice withdrawing that instruction lived on an index
  page nobody opens from a snapshot. Each now carries a dated withdrawal in its
  header and at its prohibition, naming the re-derived rate — the one edit the
  freeze rule permits, with the measurements untouched.

## Week of Oct 19–25, 2026

### Added
- **GitHub's traffic window is archived nightly, because it was the one number
  here that kept expiring** — the traffic API returns exactly 14 daily buckets
  ending yesterday and ignores pagination, so every day the window rolls, a day
  of traffic is gone for good. A nightly job writes a daily series (with
  observation and revision counts, so a settled day is distinguishable from a
  churned one) and a run ledger in which a missed night is an explicit row
  rather than an inference from silence. It prints the window value beside the
  daily sum on every run, because uniques do not add: one person over three
  days is 1 unique in the window and 3 summed across buckets. Views are
  readers; clones are CI.
- **The Zenodo v1.1.0 payload, and the publisher the notes had been describing**
  — the release notes claimed a `--staging-dir` flag the repository did not
  contain, so a fresh clone's scheduled run would have written next month's
  fingerprints over the directory the v1.1.0 receipt cites as its evidence. The
  landed script reseats staging before any read or write, refuses `--skip-build`
  without a dry run instead of reporting a pass it did not earn, splits legacy
  deposition metadata (depositions API) from files (records API, where a
  metadata PUT returns 200 and persists nothing), and keeps the two-sitting
  `--publish-only` / `--resume-draft` shapes that were actually measured. Tests
  pin the staging protection rather than assuming it.
- **The lab report has an engine** — the friction-ramps report had been repaired
  twice by hand, from throwaway scripts, so it could not be rebuilt from its own
  source. It now builds from a JSON content model, renders the PDF through Word,
  and then checks the artifact — content parity, glyph and word-spacing
  integrity, page furniture, figure identity — so a rebuild that drops a
  paragraph fails instead of shipping. Binary assets stay out of the repository,
  where a missing one is a loud failure.
- **A network-level transfer measurement, and a preregistered feel test** — one
  map tile answers a misleading question, because it slices every route through
  it: the City-Centre tile's median route carries 4 of its in-tile stops, so
  72.5% of in-tile pairs look unserved when the network serves them outside the
  clip. The new measurement works on the whole weekday network, with its
  modelling choices stated as the audit trail — a boarding is boarding a
  *pattern*, and a station is a place rather than a platform (at platform level
  45% of stops are served by exactly one pattern, an artefact of counting both
  sides of the street). The toy town's roofs became a numeric kind with floors
  derived from each roof's own seed, and the puzzle board's daily window is now
  baked into its page and exported as a Lua module for the Roblox port. The
  shipped `board.json` was deliberately not regenerated: its content already
  equals the generator's output and only the wall-clock stamp differs.
- **The public mirror got the attribution guards it had missed** — the published
  findings clone sat outside the September cleanup and carried four
  agent-trailer commits, which is why its contributor panel listed an agent
  account. It now has the hooks, its own `core.hooksPath`, and LF
  `.gitattributes` (CRLF breaks a shebang); the repository's own hook files are
  tracked executable, because git ignores a non-executable hook silently.

### Changed
- **The repository split into three siblings, and this tree keeps one
  resolver** — 449 MB tracked, 87% of it material nothing here edits: five
  frozen evidence cuts, thirteen GTFS vintages, and the university/resume stack
  that also carried identity-bearing documents next to published findings. Each
  group moved to its own private repo with the history of its paths preserved,
  reachable through env var → sibling checkout → legacy path, so a migrated
  checkout, an unmigrated one and a bare CI runner all keep working. The 66
  in-repo citations were deliberately not rewritten: the path gate resolves them
  against the sibling and otherwise reports the citation as external, and that
  exception list is the greppable record of the trade.
- **The instrument line is published from the claim registry** — one command
  writes the registered label into every surface that quotes it (32 of them),
  and a floor that trails the live count is now visible to the drift gate
  instead of only to a careful reader. The handover gate reads the same
  registry, and takes the live version from the newest entry rather than from a
  second copy of the number.
- **The changeover panel stopped re-paying a 60 s pipeline on every poll** — its
  cache was keyed on exact CSV mtimes and the collector appends every ~30 s, so
  each load rebuilt a 10.37M-row aggregation (59.3 s isolated, 151 s while
  startup warm-up ran), and date normalization made 9.36 M Python calls to
  produce ~50 distinct values. Normalizing the unique dates once and holding the
  cache for a 300 s window gives a cold 52.9 s, a post-append load of 0 s, and a
  repeat request at 0.184 s with an identical body.

### Fixed
- **CI had not executed a single backend test since the split** — every Backend
  tests run died at `ruff`, so the change that had just restructured the backend
  was never exercised by it. Seven check errors (one a live `NameError`:
  `Sequence` used without being imported) and fifteen unformatted files, two of
  which carried another lane's uncommitted edits and were formatted from `HEAD`
  instead of touched.
- **Five gates were failing on the tool instead of the data** — a template
  verifier that opened paths from the working directory and crashed when run
  from the documented one, a path gate that read a query string as part of a
  path, a publisher that knew 8 of the 14 documents carrying the headline (so
  six could drift without a gate noticing), and a resume renderer whose QR
  caption disagreed with the renderer that makes the PDFs; the fifth was a
  review wrapper that only needed formatting.
- **The retention installer acted on verdicts it was throwing away** — a unit
  that `systemd-analyze verify` rejected was installed, printed and armed anyway
  (`|| true`), and the timer's state was printed without being read, so a failed
  arming exited 0. Both verdicts are load-bearing now; the observation lock also
  learned which user owns its sidecar, so a manual run as another user fails
  loudly instead of writing the CSV unlocked.
- **The rider happy path reported only the first console error**, and its
  failure line named a status code without the resource that produced it. An
  end-to-end run is only as informative as the last error it hides.

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
- **Findings snapshot v7** (Sept 28 – Oct 4) frozen and promoted — ghost rate
  1 in 253 (89 of 22,492 verifiable trips), early departures 22.8%, AM peak
  28.8%; the cleanest collection week since the September change, all seven
  days datable after a backfill for two battery-skipped days
  ([v7](findings/findings-v7-sept28-oct4.md)).
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
  written by hand ([verification](claim-verification.md)); five more claims
  were backed by published freeze artifacts and the
  [evidence-freeze manifest](evidence-freeze-manifest.md) went out with them
  (the page has since moved to the 27-claim registry).
- **Public test suite** — 157 scrubbed test modules published so the claims
  can be audited instead of trusted, with the reproducibility framing
  corrected to match (the public repo runs no CI, so the old
  "CI-enforced coverage floor" claim is gone) inside a leak-guard and
  promotion gate.

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
- Demo trip-check crash: any API failure 404'd the whole app in demo mode —
  inline "Check failed" alert + a canonical snapshot replay instead.
- Demo "Why so slow?" view 404'd (slowness endpoints never snapshotted).
- Demo base-path incident: ad-hoc rebuilds shipped root-absolute asset
  URLs, blanking Pages since the prior refresh — rebuilds must set
  `DEMO_BASE`; rule encoded in the refresh script.
- **Transfer and trip-check correctness** — terminal-only co-location
  phantoms no longer rank as missed transfers, a cross-direction stop
  sequence bug is fixed, and planner clock labels no longer imply a walk leg
  is a bus.
- **Collector crash-safety** — writes are atomic and lock-tolerant, and one
  malformed realtime poll no longer kills a whole collection window.

---

### Measured
- **Sept-7 pre-registration FINAL verdict** — 11/10 required post-change
  weekdays collected; 4 FAIL (early-departure and AM-peak bands beaten in
  the improvement direction), 2 UNMEASURABLE (baseline tooling superseded
  mid-study, documented per-band), 1 fail-low. Verdicts and basis notes in
  the [scoreboard](../demo/).

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
