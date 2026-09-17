# Findings Snapshots — Index

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
| v4 | Sep 7 – 13, 2026 (n=7, first post-change week) | 2026-09-14T22:08Z | **CURRENT** | `findings-v4` | [findings-v4-post-sept7.md](findings-v4-post-sept7.md) |
| v5 | Sep 14 – 20, 2026 (n=7, stability window) | — | *in collection; pre-registered* | — | [pre-registration-sept14-20.md](../pre-registration-sept14-20.md) |

Notes:

- v1–v3 were frozen at the same commit during the 2026-09-03 methodology
  push; the tag for each points at the commit containing its frozen text.
- The week-over-week comparison tables inside each snapshot are filled from
  **pre-registered ranges** (see [../pre-registration-sept7.md](../pre-registration-sept7.md)
  and the v5 registration above) — predictions committed before the window's
  data existed, hits and misses recorded in place.
- Weekly feature/changelog notes live in the repo's commit history and the
  [demo banner manifest](../../demo/api-snapshot/manifest.json) vintage stamp; findings
  snapshots deliberately contain analysis only, so a methods change can never
  masquerade as a data change.

## Forecasting track record & public-dataset findings

- **[Forecasting track record](forecast-track-record.md)** — every pre-registered prediction, registered before the data existed, mechanically scored, misses published as-is. Running ledger.
- **[Route-level early-departure leaderboard](route-early-leaderboard.md)** — a new network-level finding derived entirely from the public Zenodo dataset: worst routes leave ≥2 min early on 2 of every 5 departures, best routes under 10%. Includes the reproduction one-liner and the small-n honesty table.
