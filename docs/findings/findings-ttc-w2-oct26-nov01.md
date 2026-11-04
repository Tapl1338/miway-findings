# TTC findings derivation — 2026-10-26 to 2026-11-01

> **Quotation status — added by hand 2026-11-03, after derivation.** A re-derive overwrites this block; the facts it cites live in `docs/runs/ttc-window-integrity-20261101.md`, `docs/runs/ttc-metrics-20261026.json` and `docs/findings/ttc-window-index.json`.
>
> - **Oct 26 is F4 PARTIAL, acknowledged, not passed.** 586 polls against a floor of 633 = 74%. The floor assumes one poll cadence for the week, and the cadence changed *inside* it: the poll-period fix deployed 2026-10-29 (commit `0d264456`, 86 → 129 polls/hour) lifts Oct 29–31 and so drags the window median above the days collected before it. Against its own regime Oct 26 is 86.4% (Oct 26–28 median 678 → floor 542), and 87.7% by day-obs volume against Oct 27–28. The reason is recorded in the registry's `short_day_exceptions` and printed in the receipt; **the day still reads FAIL**, it is not re-labelled.
> - **The silent-trip rates for Oct 29 – Nov 1 are NOT QUOTABLE.** They move opposite to the data: polls rose (1,023 / 792 / 1,167) and day-obs stayed high (2,763,635 / 2,143,080 / 2,647,008), while the verifiable base fell (34,952 → 33,638 → 23,901) and uncovered trips grew (2,719 → 4,033 → 8,230). Silence is tracking verification coverage, not service. Over the same three days the unmatched rate rose 6.0 → 6.3 → 7.9% (F3 flags below), and Nov 1 was dropped as degenerate — its absence from the table is the same symptom.
> - **Consequence:** the weekday aggregate (26.45%) inherits Oct 29–30 and is therefore not quotable either. **2.76% and 2.79% on Oct 27–28** are the only silent-rate figures in this window that stand on their own.
> - **Not attributed.** This is the same shape as the MiWay v11 §0.6 collapse (4,341 → 3,040 → 612 → 524 across Oct 27 – Nov 1) and no cause is claimed for either; `docs/PLAN.md` T178(d) tracks the question.

- Computed by `backend/scripts/derive_ttc_findings.py` (methods pinned in §5.2 of the two-city design: near-term rows only |horizon|<5.0 min, dedup=freshest horizon per (route,stop,dep,date), early<= -2 min, n-floor 100, bands H1<=5/H2 5-10/H3 10-20 by scheduled terminus-median headway).
- Surface vintage read: `feed_version = S1000542` (F2: callers pin this from the collector's vintage-refresh log; a rotation mid-window SPLITs the window).

## 0-I. Window integrity (per-day coverage gates, pre-registered F4)

  polls_ok window median 792; F4 PARTIAL dates: 2026-10-26: polls_ok 586 < 80% of window median 792 — date PARTIAL

## 0-II. Window row accounting (never quoted as volume)

  raw 6,542,568 -> dedup 6,542,537 -> near-term 6,135,074

## Instrument health (skeleton §5; the §0-primary-claim evidence)

  unmatched (of measurable entities): median 4.8%, mean 4.9% over 8,299,634 measurable entities
  no_predictions: median 2.9%
  zombies dropped 14,962; polls_ok 5,762 / attempted 5,762
  F3 flags: 2026-10-30: unmatched 6.0% > 5%; 2026-10-31: unmatched 6.3% > 5%; 2026-11-01: unmatched 7.9% > 5%

## Ghost / silent-trip rate (TTC construct, NEW-trip-aware)

  Rule: a scheduled trip is SILENT when no observation bound to it on its service date, and VERIFIABLE only when its route-direction was observed within +/-30 min of the trip's scheduled span that day. Unwatched trips are UNCOVERED and leave the denominator — they are never counted as ghosts.
  NEW-trip handling: rows whose schedule_relationship is not SCHEDULED are excluded from the observed set, so an inserted entity cannot stand in for a scheduled trip that did not run.
  Service-date attribution: a row is attributed to its trip's own service date — the occurrence date when that date is active for the trip's service, else the most recent active one (7-day lookback) — so a late-night trip of service date X that produces occurrence X+1 rows counts on X. The construct's input therefore spans occurrence dates through 2026-11-02 (end+1): attribution goes backward, so the window's last service date receives its after-midnight rows only if they are not cut by the occurrence window. (Keying on raw occurrence dates manufactured a 99.6% silent Tuesday and 40% unbound weekend rows in the first W1 derivation; cutting before attribution then dropped the window's last day its carry and read Sunday Oct 18 at 19.42% silent where the construct gives 8.09% (2,347 of 29,023 — measured on the 2026-10-28 re-derivation after both fixes; the first derivation's ~6% estimate was never verified against a run) — attribution is the fix, disclosed here.)

| date | scheduled | verifiable | silent | rate | uncovered | note |
|---|---:|---:|---:|---:|---:|---|
| 2026-10-26 | 37,675 | 37,430 | 4,378 | 11.70% | 241 |  |
| 2026-10-27 | 37,675 | 37,669 | 1,041 | 2.76% | 2 |  |
| 2026-10-28 | 37,675 | 37,668 | 1,052 | 2.79% | 3 |  |
| 2026-10-29 | 37,675 | 34,952 | 16,598 | 47.49% | 2,719 |  |
| 2026-10-30 | 37,675 | 33,638 | 24,903 | 74.03% | 4,033 | 66% of this service date's observation rows occur the following day (after-midnight runs) |
| 2026-10-31 | 32,131 | 23,901 | 19,851 | 83.06% | 8,230 |  |

  Weekday aggregate (Mon-Fri, excluded and degenerate dates dropped): 47,972 of 181,357 verifiable trips silent = 26.45% (1 in 4).
  Trip-id join: 100.00% of observation rows (3,580,380 of 3,580,380) carry a trip_id present in that date's scheduled feed; trip-id-less rows are never ghosts.
  Most silent trips by route (TTC-local, not a ranking): 63 (1867), 47 (1854), 512 (1412), 25 (1394), 52 (1233).
  NEW entities in the day files: new_trips = 0; SKIPPED stop announcements = 111,910 (counted by the collector, never persisted as rows).

  Limits: a trip cancelled with notice is indistinguishable from one that vanished (CANCELED entities are not persisted); a trip skipped at EVERY stop reads silent; and §5.1's time-at-anchor bind can move an observation to the adjacent trip, so two neighbours can swap silence without either having failed. Per-city figure — never compared to MiWay's trip-id construct.

## Earliness by band (near-term rows; standing caveat applies)

  Standing caveat (study design §5.1, registered 2026-09-29 pre-collection): TTC earliness share is an UPPER BOUND on true earliness — time-at-anchor binding under sub-headway lates can attach a late trip to the NEXT scheduled trip; TTC earliness and MiWay earliness are NOT the same construct.

  Band fallback: 2,857,035 near-term rows (46.57%) had no static trip to band by and took their route's modal band.

| Band | early share | late>=5m share | median lateness | n |
|---|---|---|---|---|
| H1(<=5] | 20.4% | 4.3% | -0.13 min | 23,153 |
| H2(5-10] | 25.3% | 6.3% | -0.33 min | 3,367,568 |
| H3(10-20] | 25.8% | 7.1% | -0.30 min | 1,986,129 |

  F5 schedule-anchored H1 routes excluded from earliness: 47, 510, 84, 93

  F1 (H1(<=5]): early share on pattern-verified rows 20.6% (n=12,748; 10,405 rows excluded as stop-mismatched) vs 20.4% on all rows → persists under pattern restriction

  F1 (H2(5-10]): early share on pattern-verified rows 28.0% (n=1,691,057; 1,676,511 rows excluded as stop-mismatched) vs 25.3% on all rows → persists under pattern restriction

  F1 (H3(10-20]): early share on pattern-verified rows 27.5% (n=1,030,581; 955,548 rows excluded as stop-mismatched) vs 25.8% on all rows → persists under pattern restriction

## Worst routes (TTC-local; n-floor applies)

  830: median lateness +1.25 min (n = 139)
  49: median lateness +1.17 min (n = 9,011)
  93: median lateness +0.90 min (n = 8,041)
  938: median lateness +0.82 min (n = 1,265)
  171: median lateness +0.78 min (n = 8,656)

## Claim discipline (design §0)

  Per-city block only; no cross-city row in any table; causal/comparative claims OUT OF SCOPE.

