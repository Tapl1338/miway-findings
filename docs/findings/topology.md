# System Topology — how the platform stays up 24/7

> **Provenance:** maintained in the private repo's docs as `TOPOLOGY.md`; this copy is verified token-for-token against it on every push (see *Verification layers* in the methodology page). The VPS address is deliberately withheld from the public copy — infrastructure detail, not findings.

# System Topology

## VPS Collector

The MiWay collector runs on a private cloud VPS (Oracle Always-Free tier; IP withheld) as a systemd service.

**Evidence:**
- `backend/scripts/vps/bootstrap_collector.sh:1`: Target: Oracle Always-Free AMD micro (VM.Standard.E2.1.Micro, 1 GB RAM), Ubuntu 24.04
- `backend/scripts/vps/bootstrap_collector.sh:88`: `[Unit] Description=MiWay GTFS-RT collector (always-on)`
- `backend/scripts/vps/bootstrap_collector.sh:98`: `ExecStart=/opt/miway/.venv/bin/python scripts/collect_service.py`
- `backend/scripts/vps/bootstrap_collector.sh:202`: echo "NEXT: Syncthing share of /opt/miway/data (send-only) -> laptop"

The collector uses the systemd unit `miway-collector.service` with a watchdog timer `miway-health.timer`.

The sync-canary timer `miway-canary.timer` (T104, 2026-09-16) stamps the canary beat every 5 minutes via `backend/scripts/vps/canary_beat.sh` — a single Unix timestamp overwritten in place at `/opt/miway/data/sync_canary/beat.txt`, deliberately tiny and never append-hot (the Sept-16 stall class it exists to catch). Runs as `ubuntu` (Syncthing's own user), so the beat can never recreate the root-0600 lockout.

## Syncthing Synchronization

Data flows from VPS to laptop via Syncthing in a sendonly/receive-only configuration.

**Evidence:**
- `backend/scripts/vps/bootstrap_collector.sh:202`: echo "NEXT: Syncthing share of /opt/miway/data (send-only) -> laptop"
- `docs/runs/vps-cutover-checklist.md:108`: ## Step 3 — Syncthing: data home back to the laptop
- `docs/runs/vps-cutover-checklist.md:125`: - [ ] VPS Syncthing: add folder `~/collector-data`, **Send Only**, watch
- `docs/runs/vps-cutover-checklist.md:128`: - [ ] Laptop Syncthing: accept the share, target folder
- `backend/scripts/vps/miway-canary.timer`: the 5-minute canary beat cadence
- `backend/scripts/sync_canary.py:1`: the canary decision module (beat age, 30-minute stall budget)
- `backend/scripts/cloud_deadman.py`: `_canary_check` — laptop side, SYNC STALL alerts distinct from collector-down

The VPS stamps `sync_canary/beat.txt` every 5 minutes; Syncthing ships the ~20-byte overwrite; the laptop's dead-man task (every 15 min) alerts when the mirrored beat is older than **30 minutes**. This catches a stalled sync even when the collector heartbeat looks healthy — the Sept-14/16 failure class, where the collector wrote happily and nothing arrived.

The VPS acts as Syncthing send-only, the laptop as receive-only.

## FastAPI Backend

The MiWay API runs on the laptop on canonical port 8000 with a watchdog mechanism.

**Evidence:**
- `backend/scripts/api_watchdog.py:1`: """API availability watchdog: keep the dashboard's backend answering on :8000."""
- `backend/scripts/api_watchdog.py:8`: called by scripts/windows/watchdog_api.bat every 15 minutes (task MiWayApiWatchdog)
- `backend/scripts/api_watchdog.py:38`: HEALTH_URL = "http://127.0.0.1:8000/api/health"
- `backend/scripts/api_watchdog.py:39`: PORT = 8000
- `backend/scripts/windows/watchdog_api.bat:5`: rem the MiWayApiWatchdog scheduled task (registered by
- `backend/scripts/windows/watchdog_api.vbs:3`: ' The MiWayApiWatchdog scheduled task must not flash a console window in the

The API uses Uvicorn to serve `app.main:app` on port 8000, monitored by MiWayApiWatchdog.

## Scheduled Tasks Inventory

Windows scheduled tasks are defined in `backend/scripts/windows/*.ps1` registration scripts:

| Task Name | Trigger | What It Runs |
|-----------|---------|--------------|
| MiWayApiWatchdog | Every 15 minutes | `scripts/windows/watchdog_api.bat` |
| MiWayCollector | System startup + daily | `scripts/windows/launch_collector.ps1` |
| RegisterApiWatchdogTask | N/A (registration) | `scripts/windows/register_api_watchdog_task.ps1` |
| RegisterAnalysisWatchdogTask | N/A (registration) | `scripts/windows/register_analysis_watchdog_task.ps1` |
| RegisterBackupHomeTask | N/A (registration) | `scripts/windows/register_backup_home_task.ps1` |
| RegisterBackupTask | N/A (registration) | `scripts/windows/register_backup_task.ps1` |
| RegisterDailyAnalysisTask | N/A (registration) | `scripts/windows/register_daily_analysis_task.ps1` |
| RegisterDailyDigestTask | N/A (registration) | `scripts/windows/register_daily_digest_task.ps1` |
| RegisterDailyTask | N/A (registration) | `scripts/windows/register_daily_task.ps1` |
| RegisterDeadmanTask | N/A (registration) | `scripts/windows/register_deadman_task.ps1` |
| RegisterLocalTasks | N/A (registration) | `scripts/windows/register_local_tasks.ps1` |
| DisableLaptopCollector | Manual/execution | `scripts/windows/disable_laptop_collector.ps1` |
| EnableTasks | Manual/execution | `scripts/windows/enable_tasks.ps1` |
| FeedWatch | Every 5 minutes | `scripts/windows/feed_watch.ps1` |
| LaunchCollector | Manual/execution | `scripts/windows/launch_collector.ps1` |
| MigrateDataHome | Manual/execution | `scripts/windows/migrate_data_home.ps1` |
| BackupDataHome | Scheduled | `scripts/windows/backup_data_home.ps1` |
| BatterySnapshot | Scheduled | `scripts/windows/battery_snapshot.ps1` |
| ClearAnalysisWake | Scheduled | `scripts/windows/clear_analysis_wake.ps1` |
| RenderPowerSnapshot | Scheduled | `scripts/windows/render_power_snapshot.ps1` |
| RunDailyAnalysis | Daily | `scripts/windows/run_daily_analysis.ps1` |
| WatchdogApi | Every 15 minutes | `scripts/windows/watchdog_api.bat` |
| WatchdogCollector | Every 5 minutes | `scripts/windows/watchdog_collector.bat` |

## Write Ownership

| Component | Writes To | Primary Location |
|-----------|-----------|------------------|
| VPS Collector | `/opt/miway/data/` | VPS ([IP withheld]) |
| VPS canary timer | `/opt/miway/data/sync_canary/beat.txt` (ubuntu-owned) | VPS ([IP withheld]) |
| Laptop Syncthing Receive | `%LOCALAPPDATA%\miway-optimizer\` | Laptop |
| Laptop API Watchdog | `%LOCALAPPDATA%\miway-optimizer\logs\` | Laptop |
| Laptop Analysis | `%LOCALAPPDATA%\miway-optimizer\app\data\` | Laptop |
| VPS Syncthing Send | `/opt/miway/data/` | VPS |

Evidence:
- `backend/scripts/vps/bootstrap_collector.sh:85`: `MIWAY_DATA_DIR=/opt/miway/data`
- `backend/scripts/collect_service.py:31`: `LOG_DEFAULT = config.DATA_DIR / "collector.log"`
- `backend/scripts/collect_service.py:167`: `OUT_DEFAULT = config.DATA_DIR / "obs_lateness.csv"`
- `backend/scripts/api_watchdog.py:43-47`: `_log_dir()` uses LOCALAPPDATA
- `docs/runs/vps-cutover-checklist.md:36`: - [ ] Do NOT delete the laptop's data home. It becomes the Syncthing