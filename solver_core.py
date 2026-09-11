"""CP-SAT solver core for network-wide timetable synchronization.

Owns the optimization itself:

* :func:`coordinate_descent_warmstart` — per-route warm-start offsets from a
  cheaper greedy pass, cached on the node-set digest.
* :func:`build_fleet_interlining_edges` — vehicle-block hand-offs (GTFS
  ``block_id``) that become hard layover constraints.
* :func:`select_connections` — the diversity-aware per-arriving-trip cap on
  which connections the solver sees.
* :func:`solve_transfer_sync` — the MILP/CP-SAT solve itself: per-route
  integer offsets minimising weighted wait + missed-connection headway cost,
  subject to window and fleet-layover constraints.
* :func:`per_route_impact` / :func:`wait_buckets` — result summaries.

Split from ``transfer_sync.py`` (2026-09-05); names drop the ``_`` prefix.
``transfer_sync`` re-exports the old private names for compatibility.
"""

from __future__ import annotations

import hashlib
import itertools
import logging
import math
from collections import defaultdict

import numpy as np
import pandas as pd
from ortools.sat.python import cp_model

from .geometry import haversine_m
from .lateness_reads import miss_cost_minutes

from . import config
from .transfer_types import (
    BIG_M,
    FleetEdge,
    OptimizationResult,
    TransferConnection,
    TransferNode,
)

logger = logging.getLogger("miway.solver_core")

# ---------------------------------------------------------------------------
# Coordinate descent warm-start with caching
# ---------------------------------------------------------------------------


def warmstart_cache_key(
    all_conns: list[tuple[TransferNode, TransferConnection]],
    all_routes: list[str],
    headways: dict[str, float],
    high_freq_cutoff: float,
    max_shift: float,
    buffer_minutes: float,
    t_max: float,
) -> str:
    """Generate cache key from problem inputs."""
    # Hash the connection data (fingerprint of the problem)
    hasher = hashlib.sha256()
    hasher.update(str(sorted(all_routes)).encode())
    hasher.update(
        str(
            sorted(
                [
                    (r_i, r_j, round(c.base, 2), round(c.weight, 2))
                    for _n, c in all_conns
                    for r_i, r_j in [(c.route_i, c.route_j)]
                ]
            )
        ).encode()
    )
    hasher.update(str(sorted(headways.items())).encode())
    hasher.update(str(high_freq_cutoff).encode())
    hasher.update(str(max_shift).encode())
    hasher.update(str(buffer_minutes).encode())
    hasher.update(str(t_max).encode())
    return hasher.hexdigest()[:32]


# Cache with simple dict (could use disk cache if needed)
_WARMSTART_CACHE: dict[str, dict[str, int]] = {}


def coordinate_descent_warmstart(
    all_conns: list[tuple[TransferNode, TransferConnection]],
    all_routes: list[str],
    headways: dict[str, float],
    high_freq_cutoff: float,
    max_shift: float,
    max_passes: int = 3,
    buffer_minutes: float = config.MIN_TRANSFER_BUFFER,
    t_max: float = config.T_MAX,
) -> dict[str, int]:
    """Run coordinate descent to get initial offsets for CP-SAT warm-start.

    Scans all integer shifts for each route, holding others fixed, and repeats
    until no improvement. Uses the same scoring as the MILP: weighted wait +
    missed_penalty (1 headway of departing route per missed connection).

    A connection's cost only changes when one of its two routes is the route
    being shifted, so each route's scan is a *sweep* over just the connections
    that touch it: with the partner offset frozen, the cost is piecewise
    linear in the shifted route's offset (a constant missed penalty outside the
    keep-window, ``w * wait`` inside it). Two range-add difference arrays
    recover the cost of every integer shift in
    ``O(len(conns of the route) + shift range)`` instead of re-evaluating the
    whole connection set (``O(len(all_conns))``) per candidate step.
    """
    # Check cache
    cache_key = warmstart_cache_key(
        all_conns,
        all_routes,
        headways,
        high_freq_cutoff,
        max_shift,
        buffer_minutes,
        t_max,
    )
    if cache_key in _WARMSTART_CACHE:
        return _WARMSTART_CACHE[cache_key]

    if len(all_routes) <= 1:
        return {r: 0 for r in all_routes}

    buf_int = round(buffer_minutes)
    tmax_int = round(t_max)

    # Connection data flattened once: (arriving route, departing route, base
    # wait, weight, departing headway capped at the walking alternative,
    # keep-window floor = buffer + walk).
    conn_data: list[tuple[str, str, float, float, float, int]] = []
    for _node, conn in all_conns:
        base = conn.base
        w = conn.weight
        r_i, r_j = conn.route_i, conn.route_j
        h_j = headways.get(r_j, 15.0) or 15.0
        if conn.walk_cap_minutes > 0:
            h_j = min(h_j, conn.walk_cap_minutes)
        conn_data.append((r_i, r_j, base, w, h_j, buf_int + round(conn.walk_minutes)))

    # Frozen routes (high frequency)
    frozen = set(
        r for r in all_routes if headways.get(r, float("inf")) <= high_freq_cutoff
    )

    # Busiest route for anchoring
    counts = {}
    for r_i, r_j, _b, _w, _h, _f in conn_data:
        counts[r_i] = counts.get(r_i, 0) + 1
        counts[r_j] = counts.get(r_j, 0) + 1

    anchor = max(
        (r for r in all_routes if r not in frozen),
        key=lambda r: counts.get(r, 0),
        default=None,
    )

    movable = [r for r in all_routes if r not in frozen and r != anchor]

    offsets = {r: 0 for r in all_routes}
    if anchor:
        offsets[anchor] = 0

    conns_as_i: dict[str, list[int]] = defaultdict(list)
    conns_as_j: dict[str, list[int]] = defaultdict(list)
    for idx, (r_i, r_j, _b, _w, _h, _f) in enumerate(conn_data):
        conns_as_i[r_i].append(idx)
        conns_as_j[r_j].append(idx)

    m = int(max_shift)
    size = 2 * m + 1

    def _shift_costs(route: str) -> list[float]:
        """Cost of the connections touching ``route`` for every integer shift.

        ``costs[i]`` holds the shifted route's contribution at shift ``i - m``
        (every other route keeps its current offset). ``base_prime`` absorbs
        the fixed partner offset, so ``wait = base_prime - shift`` when this
        route arrives and ``wait = base_prime + shift`` when it departs; the
        keep-window ``[lo, hi]`` in shift-space is applied with a difference
        array so the whole shift range costs O(len(conns of route) + range).
        """
        diff_a = [0.0] * (size + 1)
        diff_b = [0.0] * (size + 1)
        total_penalty = 0.0
        for idx in conns_as_i[route]:
            _r_i, r_j, base, w, h_j, floor_int = conn_data[idx]
            base_prime = base + offsets[r_j]  # wait = base_prime - shift
            total_penalty += w * h_j * 1000
            lo = math.ceil(base_prime - tmax_int)
            hi = math.floor(base_prime - floor_int)
            if lo <= hi and hi >= -m and lo <= m:
                lo, hi = max(lo, -m), min(hi, m)
                v = w * base_prime - w * h_j * 1000
                diff_a[lo + m] += v
                diff_a[hi + m + 1] -= v
                diff_b[lo + m] -= w
                diff_b[hi + m + 1] += w
        for idx in conns_as_j[route]:
            r_i, _r_j, base, w, h_j, floor_int = conn_data[idx]
            base_prime = base - offsets[r_i]  # wait = base_prime + shift
            total_penalty += w * h_j * 1000
            lo = math.ceil(floor_int - base_prime)
            hi = math.floor(tmax_int - base_prime)
            if lo <= hi and hi >= -m and lo <= m:
                lo, hi = max(lo, -m), min(hi, m)
                v = w * base_prime - w * h_j * 1000
                diff_a[lo + m] += v
                diff_a[hi + m + 1] -= v
                diff_b[lo + m] += w
                diff_b[hi + m + 1] -= w
        costs = [0.0] * size
        acc_a = acc_b = 0.0
        for i in range(size):
            acc_a += diff_a[i]
            acc_b += diff_b[i]
            costs[i] = total_penalty + acc_a + (i - m) * acc_b
        return costs

    for _ in range(max_passes):
        improved = False
        for route in movable:
            cur = offsets[route]
            costs = _shift_costs(route)
            best_i = min(range(size), key=lambda i: costs[i])
            if costs[best_i] < costs[cur + m]:
                offsets[route] = best_i - m
                improved = True
        if not improved:
            break

    _WARMSTART_CACHE[cache_key] = offsets
    return offsets


# ---------------------------------------------------------------------------
# Fleet feasibility (vehicle-block / interlining edges)
# ---------------------------------------------------------------------------
def build_fleet_interlining_edges(
    trips: pd.DataFrame,
    stop_times: pd.DataFrame,
    stops: pd.DataFrame,
    min_layover: float = config.MIN_LAYOVER_MINUTES,
    max_handoff_dist_m: float = config.BLOCK_HANDOFF_DIST_M,
) -> list[FleetEdge]:
    """Extract vehicle-block hand-off edges from GTFS ``block_id``.

    Trips sharing a ``block_id`` are worked by one vehicle in sequence. For
    every consecutive pair (A -> B) *in time* inside a block where A and B run
    different routes, the shifted schedule must keep
    ``dep_B − arr_A + offset_{r_B} − offset_{r_A} >= MIN_LAYOVER``. Edges whose
    hand-off stop is farther than ``max_handoff_dist_m`` apart (i.e. the next
    trip starts on the other side of the city) are treated as separate
    assignments and ignored. Returns an empty list when the feed has no
    ``block_id`` column (older GTFS).
    """
    if "block_id" not in trips.columns:
        return []
    st = stop_times[
        ["trip_id", "stop_sequence", "stop_id", "arr_min", "dep_min"]
    ].sort_values(["trip_id", "stop_sequence"])
    first = st.groupby("trip_id").first()
    last = st.groupby("trip_id").last()
    route_of = dict(zip(trips["trip_id"], trips["route_short_name"]))

    coords: dict[str, tuple[float, float]] = {}
    for row in stops.itertuples(index=False):
        lat, lon = getattr(row, "stop_lat", None), getattr(row, "stop_lon", None)
        if pd.notna(lat) and pd.notna(lon):
            coords[str(row.stop_id)] = (float(lat), float(lon))

    def _dist(a: str, b: str) -> float:
        ca, cb = coords.get(a), coords.get(b)
        if ca is None or cb is None:
            return float("inf")
        return haversine_m(ca[0], ca[1], cb[0], cb[1])

    edges: list[FleetEdge] = []
    blocks = trips.dropna(subset=["block_id"])
    for block_id, grp in blocks.groupby("block_id"):
        seq: list[tuple[float, str, str, str, float]] = []
        for row in grp.itertuples(index=False):
            tid = str(row.trip_id)
            if tid not in first.index or tid not in last.index:
                continue
            f_row, l_row = first.loc[tid], last.loc[tid]
            dep_first, arr_last = float(f_row["dep_min"]), float(l_row["arr_min"])
            if pd.isna(dep_first) or pd.isna(arr_last):
                continue
            seq.append(
                (dep_first, tid, str(l_row["stop_id"]), str(f_row["stop_id"]), arr_last)
            )
        seq.sort(key=lambda x: x[0])
        for (_dep_a, tid_a, last_a, _first_a, arr_a), (
            dep_b,
            tid_b,
            _last_b,
            first_b,
            _arr_b,
        ) in itertools.pairwise(seq):
            r_a, r_b = route_of.get(tid_a), route_of.get(tid_b)
            if r_a is None or r_b is None or r_a == r_b:
                continue
            handoff = _dist(last_a, first_b)
            if handoff > max_handoff_dist_m:
                continue
            edges.append(
                FleetEdge(
                    route_i=str(r_a),
                    route_j=str(r_b),
                    arr_i=arr_a,
                    dep_j=dep_b,
                    gap_minutes=round(dep_b - arr_a, 2),
                    block_id=str(block_id),
                    handoff_dist_m=round(handoff, 1),
                )
            )
    edges.sort(key=lambda e: e.gap_minutes)
    logger.info(
        "Fleet feasibility: %s interlining edges across %s blocks",
        len(edges),
        blocks["block_id"].nunique(),
    )
    return edges


def select_connections(
    all_conns: list[tuple[TransferNode, TransferConnection]],
    buffer_minutes: float = config.MIN_TRANSFER_BUFFER,
    t_max: float = config.T_MAX,
    max_connections: int | None = None,
) -> list[tuple[TransferNode, TransferConnection]]:
    """Cap the connection set fed to the MILP: diversity-aware + rescue-first.

    T01 ROOT CAUSE (node-count nondeterminism 237/238/258): the selection
    below is sorted by connection *weight* first (``all_conns`` is sorted by
    ``weight`` descending before the diverse/remainder split, and both splits
    are re-sorted by ``(rescue_potential, weight)``). Weights come from
    ``estimate_ridership_volumes`` -> ``load_ridership_rows``, which prefers
    the LIVE ``boardings_daily.csv`` (``_load_live_boardings``) whenever it
    holds >= 2 days. That file grows every collection window (the collector
    appends a route-period-day row per window), so per-route boardings
    averages shift between regenerations; the cap's weight-ordering then lets
    slightly different connections (and therefore a slightly different set of
    transfer nodes) into ``result.considered``. ``nodes_analyzed`` in
    equity-report.json counts distinct nodes in that capped set, so the
    number moves run-to-run on identical commands -- the 237/238/258 class.
    Determinism guarantee: given a FROZEN boardings snapshot the selection is
    a pure function of the input (the sort is stable and geometry-derived);
    the drift is entirely input growth. Reproducible consumers must pin the
    input via ``--data-dir`` (W05 / data_dir_util) so the weights are read
    from the frozen snapshot, not the live file.

    The cap guarantees every ``(route_i, route_j)`` pair at least one entry
    (so low-frequency feeder routes always enter the model even when lighter
    than high-frequency trunks). The remaining budget is then filled by *rescue
    potential* first -- a connection already outside ``[buffer + walk, T_MAX]`` or
    sitting right on a boundary is one a re-phase can actually improve -- and
    only then by weight.

    Weight-first-only sampling starves the model of exactly the near-miss
    connections that make the optimization do anything: the heaviest sampled
    connections are high-frequency pairs whose waits already sit inside the
    window, so the solver has nothing left to shift. Prioritising rescuable
    connections restores the movers without dropping the diverse-pair guarantee.
    """
    if max_connections is None or len(all_conns) <= max_connections:
        return all_conns

    all_conns = sorted(all_conns, key=lambda nc: nc[1].weight, reverse=True)
    seen_pairs = set()
    diverse: list[tuple[TransferNode, TransferConnection]] = []
    remainder: list[tuple[TransferNode, TransferConnection]] = []
    for item in all_conns:
        pair = (item[1].route_i, item[1].route_j)
        if pair in seen_pairs:
            remainder.append(item)
        else:
            seen_pairs.add(pair)
            diverse.append(item)

    buf_int = round(buffer_minutes)
    tmax_int = round(t_max)
    span = max(tmax_int - buf_int, 1)

    def rescue_potential(conn: TransferConnection) -> float:
        floor = buf_int + round(conn.walk_minutes)
        b = conn.base
        if b < floor or b > tmax_int:
            return 1.0  # outside the window: shifting can bring it back
        margin = min(tmax_int - b, b - floor)
        return 1.0 - margin / span  # closer to a boundary => more to gain

    remainder.sort(key=lambda nc: (rescue_potential(nc[1]), nc[1].weight), reverse=True)
    # ``diverse`` (one connection per (route_i, route_j) pair) must also be
    # ranked by rescue potential: when there are more distinct pairs than the
    # cap allows, the most fixable connections are kept. Previously only
    # ``remainder`` was rescue-sorted and ``diverse`` was first-seen by weight,
    # so once ``len(diverse)`` alone exceeded the cap the rescue logic was dead
    # code and low-weight / redundant pairs silently starved the solver.
    diverse.sort(key=lambda nc: (rescue_potential(nc[1]), nc[1].weight), reverse=True)
    return (diverse + remainder)[:max_connections]


def solve_transfer_sync(
    nodes: list[TransferNode],
    max_shift: float = config.DEFAULT_MAX_SHIFT,
    t_max: float = config.T_MAX,
    buffer_minutes: float = config.MIN_TRANSFER_BUFFER,
    high_freq_cutoff: float = config.HIGH_FREQ_HEADWAY,
    headways: dict[str, float] | None = None,
    time_limit_seconds: int = 60,
    max_connections: int | None = None,
    fleet_edges: list[FleetEdge] | None = None,
    min_layover_minutes: float | None = None,
    _allow_fleet_retry: bool = True,
    lateness_penalties: dict[str, float] | None = None,
    max_deterministic_time: float | None = None,
) -> OptimizationResult:
    """Run the multi-node MILP and return offsets + wait distributions.

    ``fleet_edges`` carries vehicle-block hand-offs (see
    :func:`build_fleet_interlining_edges`). When supplied, each edge becomes a
    hard constraint so the optimizer never shifts two interlined routes past
    each other's minimum layover.

    ``max_deterministic_time`` caps the solve in deterministic work units
    instead of (or alongside) wall-clock seconds. Wall-clock limits stop the
    search at a machine-load-dependent point, so two identical runs can
    return different offsets; a deterministic budget makes every run with the
    same feed + parameters return bit-identical results. When set, it is used
        *in addition to* ``time_limit_seconds`` (whichever expires first).

    ``lateness_penalties`` maps (route_i, route_j) tuples to a multiplier
    (0.0-1.0) derived from observed GTFS-RT miss probability. Connections that
    already fail frequently in practice get a higher miss penalty, pushing the
    solver to prioritise fixing the connections that matter most in the real world.
    """
    headways = headways or {}
    fleet_edges = fleet_edges or []
    min_layover = (
        float(min_layover_minutes)
        if min_layover_minutes is not None
        else float(config.MIN_LAYOVER_MINUTES)
    )
    layover_int = round(min_layover)

    # Flatten connections (optionally capped so very large feeds stay fast).
    # The cap is *diversity-aware*: every (route_i, route_j) pair is guaranteed
    # at least one connection before the remaining slots are filled by weight,
    # so low-frequency feeder routes always enter the model even when they are
    # lighter than the high-frequency trunk routes.
    all_conns: list[tuple[TransferNode, TransferConnection]] = []
    for node in nodes:
        for conn in node.connections:
            all_conns.append((node, conn))
    all_conns = select_connections(
        all_conns,
        max_connections=max_connections,
        buffer_minutes=buffer_minutes,
        t_max=t_max,
    )
    logger.info("Solving with %s connections", len(all_conns))

    # ---- Decision variables: one integer offset per movable route ---------
    all_routes = sorted(
        {c.route_i for _, c in all_conns} | {c.route_j for _, c in all_conns}
    )
    frozen = sorted(
        r for r in all_routes if headways.get(r, float("inf")) <= high_freq_cutoff
    )
    movable = sorted(r for r in all_routes if r not in frozen)

    # Anchor the busiest movable route at 0 to remove the trivial shift
    # symmetry (shifting every route by the same amount changes nothing).
    anchor = None
    if movable:
        counts = {}
        for _, c in all_conns:
            counts[c.route_i] = counts.get(c.route_i, 0) + 1
            counts[c.route_j] = counts.get(c.route_j, 0) + 1
        anchor = max(movable, key=lambda r: counts.get(r, 0))
        movable = [r for r in movable if r != anchor]

    model = cp_model.CpModel()
    offset_vars: dict[str, cp_model.IntVar] = {}
    for r in all_routes:
        if r in frozen:
            offset_vars[r] = model.NewIntVar(0, 0, f"offset_{r}")
        else:
            lo, hi = -round(max_shift), round(max_shift)
            offset_vars[r] = model.NewIntVar(lo, hi, f"offset_{r}")
    if anchor is not None:
        offset_vars[anchor] = model.NewIntVar(0, 0, f"offset_anchor_{anchor}")

    # ---- Fleet feasibility: vehicle-block layover constraints ---------------
    # For every interlining edge (A on route_i -> B on route_j, same vehicle),
    # the shifted gap must stay >= MIN_LAYOVER. Routes absent from ``all_routes``
    # (they feed no transfer connection the solver saw) get a pinned 0 offset,
    # so their side of the constraint is still enforced.
    baseline_fleet_violations = 0
    constrained_edges: list[FleetEdge] = []
    for edge in fleet_edges:
        gap_int = round(edge.gap_minutes)
        if edge.route_i not in offset_vars:
            offset_vars[edge.route_i] = model.NewIntVar(
                0, 0, f"offset_fixed_{edge.route_i}"
            )
        if edge.route_j not in offset_vars:
            offset_vars[edge.route_j] = model.NewIntVar(
                0, 0, f"offset_fixed_{edge.route_j}"
            )
        if edge.gap_minutes < min_layover:
            baseline_fleet_violations += 1
            # Already under MIN_LAYOVER in the base schedule. Demanding the
            # solver *repair* these within +/-max_shift made the model
            # INFEASIBLE on the real feed (dozens of such edges form
            # difference-constraint cycles whose demands exceed what a
            # +/-max_shift offset can satisfy). "Don't make it worse"
            # instead: never shrink the existing gap, but don't require a
            # repair either. A `>= 0` difference constraint is always
            # satisfiable (all offsets equal), so it cannot cause
            # infeasibility.
            need = 0
        else:
            need = layover_int - gap_int  # <= 0: keep layover >= MIN_LAYOVER
        if need > -2 * round(max_shift):
            model.Add(
                offset_vars[edge.route_j] - offset_vars[edge.route_i] >= need
            ).WithName(f"fleet_layover_{edge.block_id}")
            constrained_edges.append(edge)

    # ---- Coordinate descent warm-start ----
    # Run coordinate descent to get initial feasible offsets, then set as hints
    # for CP-SAT to speed up convergence.
    warmstart_offsets = coordinate_descent_warmstart(
        all_conns=all_conns,
        all_routes=all_routes,
        headways=headways,
        high_freq_cutoff=high_freq_cutoff,
        max_shift=max_shift,
        max_passes=3,
        buffer_minutes=buffer_minutes,
        t_max=t_max,
    )
    for r, val in warmstart_offsets.items():
        if r in offset_vars:
            model.AddHint(offset_vars[r], val)

    # CP-SAT only accepts integer coefficients, so:
    #  * times/waits are rounded to integer minutes, and
    #  * weights are scaled by 1000 then truncated to ints.
    W_SCALE = 1000
    buf_int = round(buffer_minutes)
    tmax_int = round(t_max)

    # Bound the ``wait`` domain from the model's own tolerances instead of a
    # magic 200. The missed-connection branch already pins ``wait`` to
    # [-BIG_M, BIG_M] (the kept branch to [floor, T_MAX]), and the equality
    # ``wait == base + offset_rj - offset_ri`` can only ever reach
    # ``max_abs_base +/- 2*max_shift``. The max of the two is a tight bound
    # that keeps every feasible value representable -- and, for the default
    # config, tightens the old [0, 200] domain to [-60, 60] while removing the
    # latent infeasibility of *negative* waits (a missed departure must be
    # allowed to fall before the arrival).
    max_abs_base = (
        max(abs(round(conn.base)) for _, conn in all_conns) if all_conns else 0
    )
    wait_bound = max(BIG_M, max_abs_base + 2 * round(max_shift))

    wait_exprs: list[cp_model.IntVar] = []
    miss_terms: list[cp_model.IntVar] = []
    objective_terms: list[cp_model.LinearExpr] = []
    kept_flags: list[cp_model.IntVar] = []

    for node, conn in all_conns:
        base_int = round(conn.base)
        w_int = max(round(conn.weight * W_SCALE), 1)
        wait = model.NewIntVar(
            -wait_bound, wait_bound, f"wait_{node.stop_id}_{len(wait_exprs)}"
        )
        model.Add(
            wait == base_int + offset_vars[conn.route_j] - offset_vars[conn.route_i]
        )
        missed = model.NewBoolVar(f"missed_{node.stop_id}_{len(wait_exprs)}")
        # If kept: buffer + walk <= wait <= T_MAX. If missed: no bound.
        floor_int = buf_int + round(conn.walk_minutes)
        model.Add(wait >= floor_int).OnlyEnforceIf(missed.Not())
        model.Add(wait <= tmax_int).OnlyEnforceIf(missed.Not())
        model.Add(wait >= -BIG_M).OnlyEnforceIf(missed)
        model.Add(wait <= BIG_M).OnlyEnforceIf(missed)

        wait_exprs.append(wait)
        miss_terms.append(missed)
        kept_flags.append(missed)
        objective_terms.append(w_int * wait)
        # Missing the window costs one headway of the departing route -- capped
        # at the walking alternative for short, walkable departing tails.
        miss_cost_int = miss_cost_minutes(
            headways.get(conn.route_j), walk_cap=conn.walk_cap_minutes
        )
        # Connections with high observed miss probability (real GTFS-RT data)
        # get a heavier penalty so the solver prioritises fixing the ones that
        # actually fail in practice, not just on paper.
        lateness_key = f"{conn.route_i}|{conn.route_j}"
        lateness_mult = 1.0 + (lateness_penalties or {}).get(lateness_key, 0.0)
        objective_terms.append(w_int * miss_cost_int * missed * lateness_mult)

    model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    # Stop once the incumbent is within this relative gap of the objective
    # bound. On the real feed the Saturday bound stalls at ~5.7%: rider-visible
    # savings plateau in ~15 s but the solver then burns the remaining budget
    # (up to 2× with the fleet-retry) chasing an unreachable 1% gap. 6% yields
    # identical results, certified OPTIMAL, in 40–90% less wall time. Set 0 to
    # disable and always run to the full limit.
    gap_limit = config.SOLVER_RELATIVE_GAP
    if gap_limit and gap_limit > 0:
        solver.parameters.relative_gap_limit = gap_limit
    det_budget = (
        max_deterministic_time
        if max_deterministic_time is not None
        else config.SOLVER_DETERMINISTIC_TIME
    )
    if det_budget and det_budget > 0:
        # Machine-independent stopping rule: reproducible report runs.
        solver.parameters.max_deterministic_time = det_budget
    solver.parameters.num_search_workers = config.SOLVER_NUM_WORKERS
    solver.parameters.random_seed = config.SOLVER_RANDOM_SEED
    # LP relaxation over the missed-connection disjunctions (level 2): without
    # it the objective bound stalls at ~10% on rush-hour windows and the gap
    # stop never fires; with it the same incumbents certify OPTIMAL in a
    # fraction of the budget. See config.SOLVER_LINEARIZATION_LEVEL.
    if config.SOLVER_LINEARIZATION_LEVEL != 1:
        solver.parameters.linearization_level = config.SOLVER_LINEARIZATION_LEVEL
    status = solver.Solve(model)

    # Bound gap at termination, captured BEFORE any retry/fallback re-solve
    # (it describes the model that produced the served offsets' search). For
    # OPTIMAL it is 0 by definition; for FEASIBLE it is how far the incumbent
    # is from the best bound found — surfaced on the results badge so the
    # reader sees how much headroom a time-limited run still has.
    bound_gap_pct: float | None = None
    if solver.StatusName(status) == "FEASIBLE":
        try:
            obj = solver.ObjectiveValue()
            bound = solver.BestObjectiveBound()
            if obj is not None and bound is not None and abs(obj) > 1e-9:
                bound_gap_pct = round(max(0.0, (obj - bound) / abs(obj) * 100.0), 1)
        except Exception:  # pragma: no cover - defensive: no incumbent info
            bound_gap_pct = None

    # Never serve garbage: reading solver.Value() from an unsolved model
    # returns nonsense offsets. The fleet layover constraints are a
    # non-essential refinement -- if they leave the model without a solution
    # (INFEASIBLE / UNKNOWN), re-solve without them. The connection model
    # itself is always feasible because the missed-connection flag relaxes
    # every window bound. The retry is bounded (``_allow_fleet_retry`` is
    # cleared on the re-entry), so the fallback can never recurse past one
    # level no matter how the call chain evolves.
    if (
        solver.StatusName(status) not in ("OPTIMAL", "FEASIBLE")
        and fleet_edges
        and _allow_fleet_retry
    ):
        logger.warning(
            "Fleet layover constraints left the model %s; re-solving without "
            "them to avoid serving invalid offsets",
            solver.StatusName(status),
        )
        return solve_transfer_sync(
            nodes,
            max_shift=max_shift,
            t_max=t_max,
            buffer_minutes=buffer_minutes,
            high_freq_cutoff=high_freq_cutoff,
            headways=headways,
            time_limit_seconds=time_limit_seconds,
            max_connections=max_connections,
            fleet_edges=None,
            min_layover_minutes=min_layover_minutes,
            _allow_fleet_retry=False,
        )

    # ---- Decode solution --------------------------------------------------
    # Baseline stats from original schedule (also the no-incumbent fallback).
    base_ints = [round(conn.base) for _, conn in all_conns]
    h_ints = [
        miss_cost_minutes(headways.get(conn.route_j), walk_cap=conn.walk_cap_minutes)
        for _, conn in all_conns
    ]
    # A connection is "kept" at baseline only if it already fits the window.
    miss_base = [
        1 if (b < buf_int + round(conn.walk_minutes) or b > tmax_int) else 0
        for b, (_, conn) in zip(base_ints, all_conns)
    ]

    # If the solve still has no incumbent (UNKNOWN after a hard timeout, or
    # INFEASIBLE with no fleet edges to drop), serve the as-scheduled solution
    # instead of reading solver.Value() from an unsolved model (None/garbage).
    if solver.StatusName(status) not in ("OPTIMAL", "FEASIBLE"):
        logger.warning(
            "CP-SAT returned %s; serving as-scheduled offsets",
            solver.StatusName(status),
        )
        offsets = {r: 0 for r in all_routes}
        if anchor is not None:
            offsets[anchor] = 0
        optimized_waits = list(base_ints)
    else:
        offsets = {r: int(solver.Value(offset_vars[r])) for r in all_routes}
        if anchor is not None:
            offsets[anchor] = 0
        optimized_waits = [int(solver.Value(w)) for w in wait_exprs]

    # The missed flag is derived, not chosen: a connection is "missed" iff its
    # realized wait under the chosen offsets falls outside the keep-window.
    # (``kept`` keeps the miss_terms convention: True => missed.) The solver's
    # own miss booleans can disagree with its wait assignment in early
    # incumbents, and re-deriving is always feasible and never costs more --
    # so callers get flags that provably match the returned offsets.
    kept = [
        not (buf_int + round(conn.walk_minutes) <= w <= tmax_int)  # True => missed
        for w, (_, conn) in zip(optimized_waits, all_conns)
    ]

    optimized_missed = sum(1 for k in kept if k)

    # The solver *may* return an incumbent that misses more connections than
    # the as-scheduled offsets (weighted-wait minimization happily trades a
    # few extra low-weight misses for larger high-weight savings), so a raw
    # missed-count comparison is NOT a regression. But under CPU contention a
    # truncated time budget can return an incumbent that is *dominated* by
    # doing nothing: a worse value of the very objective the MILP minimizes.
    # Only that true regression is discarded -- same formula, same weights.
    baseline_missed = sum(miss_base)
    baseline_obj = sum(
        max(round(conn.weight * W_SCALE), 1) * (be + h * mb)
        for be, h, (_, conn), mb in zip(base_ints, h_ints, all_conns, miss_base)
    )
    optimized_obj = sum(
        max(round(conn.weight * W_SCALE), 1) * (oe + h * mk)
        for oe, h, (_, conn), mk in zip(optimized_waits, h_ints, all_conns, kept)
    )
    if optimized_obj > baseline_obj:
        logger.warning(
            "Solver incumbent is dominated by as-scheduled (objective %d vs "
            "%d, missed %d vs %d); discarding it and serving as-scheduled",
            optimized_obj,
            baseline_obj,
            optimized_missed,
            baseline_missed,
        )
        offsets = {r: 0 for r in all_routes}
        if anchor is not None:
            offsets[anchor] = 0
        kept = list(miss_base)
        optimized_waits = list(base_ints)
        optimized_missed = baseline_missed

    # Record exactly which connections were fed to the model so callers (and
    # tests) can verify the T_MAX invariant over the constrained set. Kept as
    # the actual (node, connection) pairs so it aligns 1:1 with ``missed_flags``.
    considered = all_conns
    total = len(all_conns)

    # Passenger-facing effective waits: a broken connection costs one full
    # headway of the departing route on top of the standing time.
    base_eff = [b + h * mb for b, h, mb in zip(base_ints, h_ints, miss_base)]
    opt_eff = [
        int(w) + h * (1 if k else 0) for w, h, k in zip(optimized_waits, h_ints, kept)
    ]

    baseline_avg = float(np.mean(base_eff)) if base_eff else 0.0
    optimized_avg = float(np.mean(opt_eff)) if opt_eff else 0.0

    # Passenger-minutes saved (weighted): the reduction in effective passenger
    # waiting time across all connections the solver saw, in integer minutes —
    # the same quantity the MILP minimizes. Rescuing a near-missed connection
    # registers the full headway as savings.
    saved = 0.0
    for (_, conn), be, oe in zip(all_conns, base_eff, opt_eff):
        saved += conn.weight * (be - oe)

    kept_count = total - optimized_missed
    connection_health = 100.0 if total == 0 else round(100.0 * kept_count / total, 1)

    # ---- Fleet feasibility after the solve ----------------------------------
    # Re-derive the shifted layover gap for every constrained edge and count
    # violations under the chosen min-layover standard.
    optimized_fleet_violations = 0
    for edge in fleet_edges:
        gap = (
            edge.gap_minutes
            + offsets.get(edge.route_j, 0)
            - offsets.get(edge.route_i, 0)
        )
        if gap < min_layover:
            optimized_fleet_violations += 1
    block_aware = bool(fleet_edges)

    return OptimizationResult(
        offsets=offsets,
        movable_routes=movable + ([anchor] if anchor else []),
        frozen_routes=frozen,
        anchor_route=anchor,
        baseline_avg_wait=round(baseline_avg, 2),
        optimized_avg_wait=round(optimized_avg, 2),
        baseline_missed=baseline_missed,
        optimized_missed=optimized_missed,
        total_connections=total,
        total_kept=kept_count,
        passenger_minutes_saved=round(saved, 1),
        connection_health=connection_health,
        wait_distribution_baseline=wait_buckets(base_ints),
        wait_distribution_optimized=wait_buckets(optimized_waits),
        nodes=nodes,
        status=solver.StatusName(status),
        bound_gap_pct=bound_gap_pct,
        considered=considered,
        missed_flags=kept,
        interlining_edges=len(fleet_edges),
        baseline_fleet_violations=baseline_fleet_violations,
        optimized_fleet_violations=optimized_fleet_violations,
        min_layover_minutes=min_layover,
        block_aware=block_aware,
        per_route_impact=per_route_impact(all_conns, base_eff, opt_eff),
    )


def per_route_impact(
    all_conns: list[tuple[TransferNode, TransferConnection]],
    base_eff: list[int],
    opt_eff: list[int],
) -> list[dict]:
    """Per-route winners/losers: how each route's transfer waits change.

    Every considered connection sits between two routes (arriving ``route_i``,
    departing ``route_j``); a wait change affects the transferring riders of
    *both*, so each connection's weighted delta is attributed to both sides.
    The delta is the passenger-facing *effective* wait (a missed connection
    bills one full headway of the departing route), so "worse off" is a real
    rider standing longer, not a solver artifact.

    Returns rows sorted best-first (most negative weighted delta):
    route, connections, baseline/optimized weighted effective waits,
    delta_minutes (negative = riders better off), worse_off_connections,
    worse_off_max_minutes, worse_off.
    """
    acc: dict[str, dict] = {}
    for (_, conn), be, oe in zip(all_conns, base_eff, opt_eff):
        w = conn.weight
        for r in (conn.route_i, conn.route_j):
            agg = acc.setdefault(
                r,
                {
                    "connections": 0,
                    "base_eff": 0.0,
                    "opt_eff": 0.0,
                    "weight": 0.0,
                    "worse_off": 0,
                    "worst_degradation": 0.0,
                },
            )
            agg["connections"] += 1
            agg["base_eff"] += w * be
            agg["opt_eff"] += w * oe
            agg["weight"] += w
            if oe > be:
                agg["worse_off"] += 1
                agg["worst_degradation"] = max(agg["worst_degradation"], oe - be)

    rows = []
    for route, agg in acc.items():
        weight = agg["weight"] or 1.0
        base_avg = agg["base_eff"] / weight
        opt_avg = agg["opt_eff"] / weight
        rows.append(
            {
                "route": route,
                "connections": agg["connections"],
                "baseline_avg_eff_wait": round(base_avg, 2),
                "optimized_avg_eff_wait": round(opt_avg, 2),
                "delta_minutes": round(opt_avg - base_avg, 2),
                "worse_off_connections": agg["worse_off"],
                "worse_off_max_minutes": round(agg["worst_degradation"], 1),
                "worse_off": agg["worse_off"] > 0,
            }
        )
    rows.sort(key=lambda r: r["delta_minutes"])
    return rows


def wait_buckets(waits) -> list[int]:
    """Bin waits into [0-2), [2-4), [4-6), [6-8), [8-10), [10-12), 12+."""
    buckets = [0] * 7
    for w in waits:
        if w < 2:
            buckets[0] += 1
        elif w < 4:
            buckets[1] += 1
        elif w < 6:
            buckets[2] += 1
        elif w < 8:
            buckets[3] += 1
        elif w < 10:
            buckets[4] += 1
        elif w < 12:
            buckets[5] += 1
        else:
            buckets[6] += 1
    return buckets
