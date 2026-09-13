# Postmortem: lateness sync stall (Sept 8–11, 2026)

**Status:** resolved · **Severity:** silent replication gap, 3 days · **Data destroyed:** none
**Author:** the project's operator, with his AI pair (diagnosis + writeup)

## Timeline

- **Sept 8, ~20:15** — collector cutover to a cloud VPS. The historical
  `obs_lateness.csv` was seeded onto the VPS by hand, using a root shell.
- **Sept 8 → Sept 11** — the collector appended ~36 MB of new lateness
  observations on the VPS. The file-sync service (running as an unprivileged
  user) could not read the seeded file, so **none of it reached the analysis
  machine**. Coverage windows, vehicle snapshots and alerts — files created
  by the collector service itself, world-readable — kept syncing normally,
  so every "is collection alive" signal looked healthy.
- **Sept 11, ~12:45** — while capturing dashboard screenshots for this
  repository, the Home view's own freshness badge read **"lateness data
  2 d 15 h old."** That did not match the collector's health metrics, and
  the mismatch is what started the investigation.
- **Sept 11, ~13:00** — compared file size and mtime at both ends: VPS copy
  current (142 MB, written minutes earlier); laptop copy frozen at the Sept 8
  seed. File mode on the VPS: `600 root:root`. Sync user: not root. Root cause
  found.
- **Sept 11, evening** — one command (`chmod a+r` as root) opened the file.
  The sync service caught up **within a minute** (36.9 MB); the laptop's last
  row now carries the same date as the VPS. Verified and closed.

## Root cause

A hand-planted file was copied with an elevated shell, leaving permissions
that the unprivileged sync user could not read. The cutover checklist verified
that the collector *service* was healthy and that *window* files were syncing
— it never verified that *every* file in the data home was readable by the
sync user. Append-mode writes by the collector preserved the restrictive mode
indefinitely; nothing ever failed loudly.

## Impact

- 3 days of lateness observations invisible to the analysis home (and to the
  daily analysis task). All data survived on the VPS and in its nightly
  backups — **no data was lost**, the replication was just one-way-broken.
- The platform's freshness badge understated data age by ~2.5 days; had this
  continued, weekly analyses would have quietly run on stale observations.

## What worked

- **The dashboard's own trust view.** The data-vintage badge — built weeks
  earlier so the numbers could be audited — caught a failure no alert was
  configured to catch, because "every other file syncs" made the pipeline
  look healthy. Monitoring that shows the *age of what you actually have*
  beats monitoring that shows whether processes are running.
- End-to-end verification habit: comparing sizes/mtimes on both sides took
  five minutes and settled the diagnosis.

## Action items

1. **(done)** File opened to the sync user; sync verified current and keeping pace.
2. **(done)** Runbook rule added: anything planted into the data home by hand
   is copied as the sync user, or followed by an explicit permission fixup.
3. **(todo)** The daily analysis task should *assert* data freshness — fail
   loudly if the newest observation is older than a threshold — instead of
   silently recomputing on whatever it was given.
4. **(done)** This document exists because "found and fixed our own
   infrastructure's silent failure" belongs in the correction log, not in
   a private chat.
