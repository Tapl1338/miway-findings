# Sample versioning policy — frozen deposits, versioned re-cuts

## The rule

**Once the DOI mints, v1.0.0 is frozen forever.** No edits, no re-uploads
to the same record, no "small fixes." Corrections happen as a *new
version* of the same Zenodo record (Zenodo versions share one concept DOI;
each version gets its own version DOI). This is the same discipline as the
findings snapshots: immutable once published, corrections go forward, not
backward. It's also the exact anti-pattern this project exists to catch —
silent post-publication edits — so it can't be committed by us either.

## What "frozen" binds

The CSV and the README's processing-rules section are frozen. The repo's
`data/README.md` is **not** frozen — it is the living portal: it stays
pointed at the newest version, keeps the provenance table for the newest
cut, and accumulates a version table (below) linking every past version
DOI. One authoritative home per artifact, like the changelog rule.

## Versioning scheme

`vX.Y.Z` — semver, mirroring the findings snapshots' weekly cadence but
driven by *content*, not the calendar:

| bump | trigger | example |
|---|---|---|
| **Z (patch)** | metadata fix only (typo, clearer wording); **no new data rows, no rule change** | abstract misspells a number |
| **Y (minor)** | **content re-cut from newer corpus**: bigger n, later span, same rules | quarterly re-cut with the same pipeline |
| **X (major)** | **rule change**: new dedup basis, new filter, schema change, changed seed convention | the empty-date fix itself would have been a major |

Rule changes are never retrofitted into a minor re-cut: a reader must be
able to diff two versions of the dataset and know from the version alone
whether the *rules* changed or only the *window*.

## Re-cut procedure (the T112 pipeline, reused verbatim)

1. `python backend/scripts/make_public_sample.py` (private repo) — same
   seed, same gates (0 empty dates / 0 forecasts / exact n).
2. **Never overwrite the old CSV in place.** The new cut lands as
   `lateness-sample-250k-vX.Y.Z.csv` (or a new basename if schema changes),
   the old file is kept for the repo's history; Zenodo's version upload
   receives only the newest file set.
3. Update `data/README.md`: provenance table (input SHA, funnel counts,
   output SHA), span, counts — and add the version row to the table below.
4. `git tag data-vX.Y.Z` at the commit where the new CSV landed, push the
   tag. (Mirrors the `findings-vN` snapshot tags.)
5. Upload to the *existing* Zenodo record as a new version; paste the new
   version DOI into the version table.

## Cadence

Not weekly — content-driven. Suggested: **minor re-cut at the end of each
major data era** (after a service change settles, e.g. post-Oct-26), or
when the corpus doubles. A re-cut only earns a version if someone would
plausibly cite it; otherwise the repo's live sample is enough and the DOI
stays at v1.

## Version table (maintained in this file AND in data/README.md)

| version | window | n | rules delta | artifact SHA-256 | DOI | status |
|---|---|---|---|---|---|---|
| v1.0.0 | 2026-08-23 → 2026-09-15 | 250,000 | initial (dated-actuals, seed 20260911) | `433875dc3cc709931f5213cb8b0449192fc80ebb666de0c833d1500e3f4e4613` | *FILL after publish* | in preparation |

## One deliberate asymmetry

The **findings snapshots** freeze weekly *analysis*; the **dataset
version** freezes the *evidence base*. They move on different clocks on
purpose: an analysis week can cite dataset v1 even while the repo's live
sample has moved on, so no frozen finding ever points at a moving number.
