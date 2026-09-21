# Findings Snapshots — Index

> **New in the interactive demo:** *Early departures* (route-level early-leaving, from the public sample) and the *Forecast scoreboard* (every pre-registered prediction, mechanically scored). Both under Network health in the sidebar.

Every weekly snapshot is **immutable once frozen**: the file is never edited
after its freeze date; corrections happen in the *next* version (or, for
typos, are flagged inline without touching numbers). Each version is also
pinned with a git tag — `git show findings-v4` always returns the exact
frozen text, and `git diff findings-v3 findings-v4` shows precisely what a
week of new data changed.

| Version | Window | Frozen | Status | Tag | Link |
|---|---|---|---|---|---|
| v1 | Aug 17 – 23, 2026 (n=7) | 2026-09-03 | superseded by v2 | `findings-v1` | [findings-v1-n7-aug17-23.md](../findings-v1-n7-aug17-23.md) |
| v2 | Aug 24 – 30, 2026 (n=7) | 2026-09-04 | superseded by v3 | `findings-v2` | [findings-v2-n7-aug24-30.md](../findings-v2-n7-aug24-30.md) |
| v3 | Aug 31 – Sep 6, 2026 (n=7) | 2026-09-07 | superseded by v4 | `findings-v3` | [findings-v3-n7-aug31-sep06.md](../findings-v3-n7-aug31-sep06.md) |
| v4 | Sep 7 – 13, 2026 (n=7, first post-change week) | 2026-09-14T22:08Z | superseded by v5 | `findings-v4` | [findings-v4-post-sept7.md](findings-v4-post-sept7.md) |
| [Era comparison](feed-era-2017-vs-2026.md) | 2017-03-08 vs 2026-10-06 (pinned feeds) | 2 feeds | Current |
| [Sept 7 schedule diff](sept7-schedule-diff.md) | 26AU03 vs 26SE07 (same combined zip) | static GTFS | Current |
| [Route 87 redundancy audit](route-87-redundancy-audit.md) | 2017 / 2023 / 2024-01 / 2026 feed vintages | 4 feeds | Current |
| [Route 34 redundancy audit](route-34-redundancy-audit.md) | schedule arithmetic vs the 35 | — | Current |
| v5 | Sep 14 – 20, 2026 (n=7: 6 complete + 1 partial day) | 2026-09-21T21:20Z | **CURRENT** — second post-change week | `findings-v5` | [findings-v5-sept14-20.md](findings-v5-sept14-20.md) |

Notes:

- Rates are computed from deduplicated end-of-window data, never from
  mid-window snapshots: within a live collection window the raw file holds
  multi-poll repeats of every active trip (~10x end-of-window size), and a
  mid-window read is not a smaller sample of the truth — it is a different,
  wrong one.


- v1–v3 were frozen at the same commit during the 2026-09-03 methodology
  push; the tag for each points at the commit containing its frozen text.
- The week-over-week comparison tables inside each snapshot are filled from
  **pre-registered ranges** (see [../pre-registration-sept7.md](../pre-registration-sept7.md),
  the [v5 registration](../pre-registration-sept14-20.md), and the
  [v6 registration](../pre-registration-sept21-27.md)) — predictions committed
  before the window's data existed, hits and misses recorded in place.
- Weekly feature/changelog notes live in the repo's commit history and the
  [demo banner manifest](../../demo/api-snapshot/manifest.json) vintage stamp; findings
  snapshots deliberately contain analysis only, so a methods change can never
  masquerade as a data change.

## Forecasting track record & public-dataset findings

- **[Forecasting track record](forecast-track-record.md)** — every pre-registered prediction, registered before the data existed, mechanically scored, misses published as-is. Running ledger. Interactive: demo sidebar → *Forecast scoreboard*.
- **[Route-level early-departure leaderboard](route-early-leaderboard.md)** — a new network-level finding derived entirely from the public Zenodo dataset: worst routes leave ≥2 min early on 2 of every 5 departures, best routes under 10%. Includes the reproduction one-liner and the small-n honesty table. Interactive: demo sidebar → *Early departures*.
