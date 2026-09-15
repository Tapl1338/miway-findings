> **Provenance:** the private repo's quality-improvement plan (`QUALITY-PLAN.md`), promoted verbatim; verified token-for-token on every push. Published as-is — targets, phases, and the "deliberately does NOT do" list included — because the plan's honesty is the point.

# Quality Improvement Plan

_Status: proposed 2026-09-02 · Baseline: 642 fast tests green, ~16.0k app LOC / ~15.8k test LOC, `ruff check` green (E722/B904 re-enabled), `ruff format` red on 3 files, no coverage measurement, no backend typechecker, sanitized-500 helper in place but not centralized._

This plan operationalizes the 2026-09-02 backend review (7.5/10) and the four-dimension
audit (SPEC 6 / DESIGN 6 / CORRECTNESS 7 / QUALITY 6). It is sequenced so every phase
leaves the tree green, and every item has a measurable acceptance criterion.
"Verify" always means the command shown, run locally **and** in CI — not intent.

---

## Scorecard (the numbers this plan moves)

| Metric | Today | Target | Phase |
|---|---|---|---|
| Line coverage (backend `app/`) | unmeasured | ≥ 70% engine, ≥ 90% routers | 1 |
| `ruff format --check .` | red (3 files) | green in CI | 1 |
| Sanitized-500 sites owned by one handler | 0 (18 per-endpoint copies) | 1 app-level handler | 2 |
| Per-endpoint try/except wrappers | ~35 | 0 (except genuine partial-cleanup) | 2 |
| Regression test for error sanitization | none | 1 fault-injection test | 2 |
| Largest module | `transfer_sync.py` 3,180 ln | ≤ 800 ln per module | 3 |
| Backend static typing | none | mypy on `app/routers` + new modules | 4 |
| Duplicated unknown-period 422 branches | 5 | 1 shared dependency | 2 |
| SQLite store connection layer | 2 copies (`state_store`, `job_store`) | 1 shared module | 3 |
| Known drift: README ops defaults vs code | 3 documented divergences | 0 | 5 |

---

## Phase 0 — Restore the gates (≤ 1 hour)

The tree currently fails the project's own CI format check. Nothing else matters
until the gates are trustworthy again.

1. `ruff format` the three flagged files (`app/routers/operations.py`,
   `app/routers/service_quality.py`, `app/routers/transfers.py` — all from the
   concurrent agent's in-flight edits, none from this plan's author).
2. Confirm `ruff check . && ruff format --check .` locally, then let CI confirm.

**Accept:** CI backend job green on master. **Verify:** `ruff format --check .` exits 0.

---

## Phase 1 — Measure before refactoring (≤ 1 day)

No refactor in Phase 2–3 may proceed without a coverage baseline, or "green tests"
becomes "the tests I happened to still pass".

1. Add `pytest-cov` to requirements; in `ci.yml` run
   `pytest -m "not slow" -n 4 --cov=app --cov-report=term --cov-report=xml`.
2. Publish the XML to Codecov or store the artifact; print a per-module table.
3. Add a CI comment (or job summary) so every PR shows coverage delta.
4. Optionally add `--cov-fail-under=<baseline-5>` and ratchet upward — start honest,
   not aspirational.

**Accept:** coverage number exists, is visible per-PR, and cannot silently drop.
**Verify:** open a PR deleting one line from `app/reliability.py` → coverage moves.

---

## Phase 2 — One owner for error handling (≤ 1 day)

This is the audit's single highest-value pass: it closes a DESIGN gap (one owner per
behavior), a SPEC gap (default-on sanitization + regression lock), and a QUALITY gap
(~120 lines deleted), and it converts the unexercised new behavior into an observed one.

1. Add `@app.exception_handler(Exception)` in `main.py` (or a tiny
   `app/error_middleware.py`) that: logs with `logger.exception`, returns
   `{"detail": "<contextual message> (see server logs)"}` with a
   `X-Error-Id` header, and optionally correlates the id in the log line.
2. Re-raise semantics must be preserved: `HTTPException` (422/404/429/…) must never
   be swallowed — assert this with a test hitting `/api/transfer/nodes?period=bogus`.
3. Delete the ~35 per-endpoint `except Exception` wrappers that only re-wrapped
   `internal_error`; keep `internal_error()` in `app/errors.py` for the handful of
   sites that genuinely partial-clean (e.g. job-store rollback in `transfers.py`,
   `_ASYNC_SLOTS.release()`) and for `equity._compute_equity_from_stored` until it
   is folded in.
4. Fold equity's hand-rolled sanitized message into the same handler.
5. Add the **fault-injection test**: monkeypatch `prepare_feed` to raise
   `RuntimeError("SECRET internal path ...")`, call an endpoint, assert
   500, assert `"SECRET" not in body`, assert detail matches the `(see server logs)`
   contract. This is the regression lock the audit flagged as missing.
6. While touching validation: replace the 5 duplicated unknown-period `422` branches
   with one FastAPI dependency or `Path`/`Query` enum (`Literal[*TIME_PERIODS]`).

**Accept:** one grep finds exactly one `except Exception` owner; fault test red on
revert. **Verify:** `pytest tests/test_error_sanitization.py -q` (new) + full fast suite.

---

## Phase 3 — Split the monoliths (2–4 days, highest risk — do after Phase 1)

`transfer_sync.py` (3,180 ln) and `circuity_analyzer.py` (2,222 ln) each mix three
concerns. Split **mechanically, not creatively** — this phase changes structure, zero
behavior. The 1:1 test LOC is the safety net; the coverage baseline from Phase 1 is
the map of what the tests actually cover (audit the gaps *before* moving code).

`transfer_sync.py` → package `app/transfer_sync/`:

| Module | Moves | ~ln |
|---|---|---|
| `graph.py` | `build_transfer_nodes`, `build_nodes_for_window`, `_cached_node_build`, terminal/stop-name canonicalization | ~1,100 |
| `solver.py` | `solve_transfer_sync`, CP-SAT model, BIG_M, offset application | ~700 |
| `projection.py` | `project_ridership_impact`, ridership weighting, period-share floor | ~500 |
| `queries.py` | `find_worst_missed_connections`, headways, top-missed helpers | ~400 |
| `__init__.py` | re-export the public surface **unchanged** | ~20 |

Public-API contract: every `from .transfer_sync import X` in routers/scripts/tests
must keep working — the package re-exports. Same treatment for `circuity_analyzer.py`
(`geometry.py` shapes+lengths, `splits.py` trunk/feeder proposals, `corridor.py`
splice/segmentation, `report.py` GeoJSON/summary).

Rules for this phase:
- One commit per extracted module, full fast suite between each.
- No signature changes, no renames beyond module path, no "small cleanups" mixed in.
- Run the nightly slow suite once at the end (solver tests are the real validator).

**Accept:** no module > 800 ln; `python -c "import app.main"` unchanged; nightly green.
**Verify:** `pytest -m "not slow" -n 4 -q` after each extraction + `pytest -m slow` at end.

---

## Phase 4 — Types and deduplication (2–3 days, parallelizable)

1. **Shared SQLite layer.** `state_store.py` and `job_store.py` duplicate the
   connection-per-call + global lock + WAL pragma pattern. Extract `app/db.py`:
   `_connect()` (timeout, WAL, schema idempotent) and a `locked_write(fn)` helper.
   Both stores keep their public functions; ~60 lines deleted, one owner for the
   locking decision. Verify: existing `test_async_jobs.py` + state-store tests green.
2. **mypy, incrementally.** Add `mypy` to requirements + CI. Enable strictly on
   `app/routers/`, `app/models.py`, `app/errors.py`, `app/db.py` and the Phase-3
   modules; leave the two big analysis engines loose initially and tighten as
   Phase 3 splits them. Verify: `mypy app/routers app/models.py` exits 0.
3. **Health endpoint out of `main.py`.** Move the feed-count cache + freshness scan
   into `app/routers/health.py`; `main.py` becomes pure composition. The TTL/lock
   logic from the earlier fix moves with it unchanged.
4. **Rate limiter config.** The concurrent agent's `__import__("os")` inline imports
   in `transfers.py` should move to `config.py` as ordinary env-tunables
   (`MIWAY_RATE_LIMIT_WINDOW` / `MAX_POST`), matching every other knob's pattern.

**Accept:** `mypy` green on the strict set; `app/db.py` is the only module importing
`sqlite3` under `app/`. **Verify:** `mypy <strict set>` + fast suite.

---

## Phase 5 — Documentation truth and repo hygiene (≤ 1 day)

1. Fix the REDFLAG §4 drift: README collector-window defaults vs
   `collect_service.py` (README says "AM+PM peaks", code collects ~19h incl.
   00:00–02:00), `MIWAY_COLLECT_DAYS` example, stale sidebar panel list.
2. `docs/methods-appendix.md:120` documents `build_transfer_nodes(...,
   same_terminal_walk=True)` as a usable toggle — either wire it through
   `build_nodes_for_window` or label it "engine-level, not reachable via API"
   (REDFLAG §2). Decide, don't leave both.
3. Resolve the two "all day" definitions (REDFLAG §5): `TIME_PERIODS["all_day"]`
   starts 06:00 but `OptimizeRequest.window_start` defaults 0.0 — align the schema
   default to the period window or document the divergence at both sites.
4. Delete dead weight found along the way: `wire_clean.py`, `verify_t20.py`,
   `_anomaly_*.py` (already staged for deletion by the other agent), duplicate
   docstring paragraph in `warmup.py` (lines repeat verbatim).

**Accept:** a reader following README ops instructions gets the code's behavior.
**Verify:** each README command copy-pasted and run once.

---

## Phase 6 — Continuous hardening (ongoing, no deadline)

Ordered by expected defect-prevention per hour spent:

1. **Property/invariant tests for the solver.** Offsets stay within max_shift; every
   connection either meets T_MAX or is marked missed; shifting a frozen route is
   impossible. These are cheap `hypothesis` invariants over small synthetic feeds
   and would have caught REDFLAG §3's phantom-transfer class.
2. **Phantom-transfer fix + regression test** (REDFLAG §3, data-confirmed):
   cap same-name grouping by distance. Highest *correctness* value in the repo —
   it currently feeds zero-walk 4.8 km connections into the MILP objective and
   every councillor-facing number.
3. **Pre-commit hooks** (`.pre-commit-config.yaml`): ruff check + format on changed
   files. Turns CI failures into local ones, ~15 min setup.
4. **Structured request-ID logging** (middleware + format), so the sanitized 500's
   `X-Error-Id` from Phase 2 correlates with the server traceback. Small, and it
   makes the sanitization contract genuinely operable.
5. **Frontend vitest coverage** of the error paths: at least one test per panel that
   the human-readable 500 detail renders instead of a blank card.

---

## What this plan deliberately does NOT do

- **No framework swaps, no Redis/multi-worker hardening.** The in-memory rate limiter
  and single-process assumption are documented PoC constraints; they are a rewrite
  trigger, not a quality gap, until someone actually deploys >1 worker.
- **No test-count targets.** The suite is already at 1:1 test/app LOC; more tests
  without new coverage information is theater. Phase 1 exists to make "more tests"
  measurable.
- **No comment/docstring reduction pass.** The verbose evidence-citing comments are
  the project's best quality feature, not debt.

## Sequencing logic

Phase 0 restores trust in the gates; Phase 1 makes every later claim measurable;
Phase 2 is the audit's named highest-value pass and is low-risk; Phase 3 is the
expensive structural work that Phase 1's coverage map de-risks; Phase 4 rides on
Phase 3's smaller modules; Phase 5 pays down the audit ledger before it rots;
Phase 6 converts one-time fixes into standing defenses. Phases 2 and 4 are safe to
interleave with 3 for multiple agents; Phase 3 itself must be single-threaded.
