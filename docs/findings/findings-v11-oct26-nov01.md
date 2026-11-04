# Findings snapshot v11 — eighth post-change week (Oct 26–Nov 1) — **DATA GAP, NOT QUOTABLE**

> **Public copy (2026-11-04).** A window that cannot be measured is labelled in
> public rather than silently skipped; this page carries **no** quotable metric
> (see §1) and exists so the gap is visible. The host address, absolute paths
> and the collector command lines are withheld from this copy — every figure is
> unchanged.
> **Status: FROZEN 2026-11-02.** Derived from the evidence freeze
> `evidence-freeze-v11/` (dry run and real run both `6 frozen, 0 skipped,
> 0 missing`) via the pinned pipeline
> `derive_findings.py --start 2026-10-26 --end 2026-11-01 --source freeze
> --freeze-dir …/evidence-freeze-v11` (exit 0). The derivation's output is
> cited here **only to show that it is unusable** — see §0.5.
> **This file carries no headline number.** It exists so the window is
> labelled rather than silently skipped, and so the next session starts from
> the cause instead of re-deriving it.

## 0. Window integrity — why this week cannot be measured

1. **The observation corpus has no rows for six of the seven days.** In the
   v11 freeze, `obs_lateness.csv.gz` (87,576,642 B compressed;
   `obs_lateness.csv` 374,704,674 B, sha256 prefix `ac7c5f7c27b8c0a4`) holds
   **10,398,891 rows across 66 distinct dates**, and its newest service date
   is **2026-10-26 with 3,697 rows**. Window rows total **3,697**: that one
   partial day. A normal weekday in the same file is 196,178–205,031 rows
   (Oct 19–23). There are **zero** rows for Oct 27, 28, 29, 30, 31 and Nov 1.
   Command: per-`date` row count over the frozen `.gz` (streamed, no
   extraction).

2. **Cause, proven rather than inferred: the collector's static GTFS board
   expired on Oct 25.** On the collector host the collector loads
   `LOCAL_GTFS_DIR`, the static-board directory —
   an extract written **2026-09-09** whose `feed_info.txt` says
   `20260805,20261025`, whose `calendar_dates.txt` ends at **20261025**, and
   whose trips carry only the `26SE07-` service prefix. From Oct 26 no trip
   in that board is scheduled, so every real-time entity is unmatched and no
   observation row can be built. The journal shows the transition to the
   poll: the **00:00–06:00** window on Oct 26 still wrote `obs=+32978` — the
   tail of Oct 25's night service, which is why the taper looks gradual —
   and **every window after it wrote `obs=+0`**, while polls, vehicle
   snapshots and alerts stayed healthy (`polls=350/350 … 705/705`,
   `vp` equal to polls, `alerts=47–56` per window).

3. **Why nothing refreshed it.** `app/gtfs_loader.load_feed()` downloads only
   when files are **missing** (`_missing_files()`); `data/gtfs/` has been
   populated since 2026-09-09, so a feed that went *stale* was never noticed.
   The live feed was current the whole time, so this was not the vendor's
   fault: fetched 2026-11-02, `7,725,078 B`, sha256 `4f5cabf486244430…`,
   `feed_info` **20260922 → 20261220** (version 2), service prefixes
   **`26SE07` and `26OC26`**, 112 service-date rows dated on/after Oct 26.

4. **The monitoring gap that let eight days pass silently.** Five timers run
   on that box (`miway-healthcheck`, `miway-canary`, `miway-health`,
   `miway-keepalive`, `miway-backup`) and **none of them reads
   `feed_end_date`**. Every health surface watched whether the collector was
   *polling*, and it was; nothing watched whether it was *writing*. The
   freeze script's own precondition passed for the same reason — it checks
   the analysis chain's exit status and the timestamp, not whether the
   declared window contains evidence.

5. **What the deriver produces, and why none of it is quotable.** The pinned
   command ran clean (exit 0) and reported: ghost trips **382 of 18,938
   verifiable (1 in 50)** against v10's **179 of 33,916 (1 in 189)**;
   earliness **27.3% of departures ≥2 min early (n = 3,697)**; AM peak
   **"no AM data"**; crowding explicitly collection-wide (no date column),
   not windowed. Each figure is an artifact of the gap, not a measurement of
   the week:
   * the ghost denominator is 44% smaller than v10's, and 267 of the window's
     382 ghosts sit on **Nov 1**, whose verifiable base is **524** against
     **2,715** for the previous Sunday;
   * the earliness rate is computed on the **3,697-row Oct-26 sliver** — the
     tail of one night's service, i.e. the overnight service pattern;
   * the crowding block says in its own text that it is not windowed.
   Full output: `findings-v11-derivation-20261102.md` (private repo; the figures
   above are its own summary).

6. **A second anomaly, stated without a cause.** The ghost ledger's
   verifiable base falls 4,341 (Oct 27) → 3,040 (Oct 28–30) → 612 (Oct 31) →
   524 (Nov 1), against 5,564 / 3,381 / 2,715 in the prior week. The vehicle-
   position window files for those dates exist and are 4.5–22.2 MB each, so
   this is not "no snapshots" in the obvious sense, and the mechanism is
   **not** established here. No number derived from that base is quoted, and
   it is logged as its own open question rather than folded into the gap
   explanation.

## 1. What this snapshot is not

It is not a measurement of Oct 26–Nov 1, and it must not be cited as one. It
carries no headline, no route ranking, and no ghost rate. Anything a reader
needs from this week is unavailable, not zero: a zero here would claim the
buses did not run, which the vehicle-position record contradicts.

## 2. What has to happen before v12

1. **Refresh the board on the collector host** (the live `google_transit.zip`
   into the board directory) and restart the collector; the corpus resumes from
   that point, and nothing recovers Oct 26–Nov 1 — those observations were
   never written.
2. **Add a feed-expiry alarm.** `feed_end_date` (or max `calendar_dates`
   date) older than *today* is a hard failure, not a note: it is the only
   signal that would have caught this, and every existing check passed while
   the corpus was empty.
3. **Resolve §0.6** (the weekend verification collapse) before the next
   window's ghost numbers are quoted, because the same collapse would
   silently deflate a healthy week's denominator too.

## 3. Reproduction

```
# the gap, from the frozen cut
python -c "import gzip,csv,collections;c=collections.Counter();[c.__setitem__(r['date'],c[r['date']]+1) for r in csv.DictReader(gzip.open('obs_lateness.csv.gz','rt',encoding='utf-8',errors='replace'))];print(sum(c.values()),max(c),c[max(c)])"

# the cause, on the collector host (address and absolute paths withheld)
cat "$LOCAL_GTFS_DIR/feed_info.txt"; cut -f2 -d, "$LOCAL_GTFS_DIR/calendar_dates.txt" | sort | tail -1
journalctl -u miway-collector --since '2026-10-26 05:00' | grep 'WINDOW COMPLETED' | head -4

# the feed was never the problem
curl -sS -o /tmp/live.zip https://www.miapp.ca/GTFS/google_transit.zip && python -c "import zipfile;z=zipfile.ZipFile('/tmp/live.zip');print(z.read('feed_info.txt').decode().splitlines()[1])"
```

Freeze receipt: `evidence-freeze-manifest.md`, six rows stamped
`2026-11-03T02:13Z` (UTC; 2026-11-02 21:13 local) labelled `v11`.
