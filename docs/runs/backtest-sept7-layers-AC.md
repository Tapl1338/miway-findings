# Backtest Layers A & C — mechanical re-derivation of the Sept-7 pre-registration

Generated 2026-09-24T22:50:16.704223+00:00. Bands quoted verbatim from the frozen pre-registration; no band adjusted to fit an outcome.

| Layer | Metric | Band (frozen) | Measured | Verdict |
|---|---|---|---|---|
| A | Early-departure share (>=2min early), post weeks | 29-33% | W1 21.16% (n=1,146,526); W2 21.16% (n=1,196,073) | **FAIL-LOW** |
| A | AM-peak (07:00-09:00) early share | 35-39% | W1 25.54% (n=119,871); W2 25.99% (n=127,887) | **FAIL-LOW** |
| A | Route 2 midnight avg load (pre-reg basis: period mean) | 40-44% | pre 42.5 -> post W1 44.8 | **FAIL-HIGH** |
| A | Route 109 PM-rush avg load / SRO | 38-42% avg; 20-24% SRO | pre 41.7% -> post W1 41.7% (SRO 13.0%) | **PASS** |
| A | Routes >=33% full after 19:00 (count) | 5-7 | pre 3 -> post W1 9 (101, 109, 110, 126, 2, 6, 61, 66, 73) | **FAIL-HIGH** |
| A | Ghost-trip rate | 2.5-3.5% | post W1 1-in-255 (121/30,848); W2 1-in-272 (109/29,605) | **FAIL-LOW** |
| A | Network saved_pax_minutes (solver, post basis) | 9,500-10,000 | 9714.6 (basis 20260911, 2026-09-19T23:48:19Z) | **PASS** |
| A | Network base_avg_wait | 18.5-19.0 | 19.12 | **FAIL-HIGH** |
| A | Ward 9 delta/worse-off | +1.5..+3.5 min; 13-17 of 21 | no like-for-like post run (20260922 reruns used a different stop universe: 5/14 stops) | **UNSCOREABLE** |
| C | Pair 43->109 realized-wait delta | - | NaN | **UNSCOREABLE** |
| C | Pair 109->43 realized-wait delta | - | NaN | **UNSCOREABLE** |
| C | Pair 10->43 realized-wait delta | - | NaN | **UNSCOREABLE** |
| C | Pair 45->109 realized-wait delta | [-1.5, -0.5] | -3.34 | **FAIL-LOW** |
| C | Pair 313->43 realized-wait delta | - | NaN | **UNSCOREABLE** |
| C | Pair 38->43 realized-wait delta | - | NaN | **UNSCOREABLE** |
| C | All other Meadowvale pairs flat (+-0.5) | within +-0.5 | 75/88 violate; worst degradations [('13->46', 2.7), ('44->46', 2.42)] | **FAIL** |
| C | Guardrail: 45->109 no increase >1 min | <= +1.0 | -3.34 | **PASS** |
| C | Guardrail: no pair degrades >2 min (UNSCOPED) | <= +2.0 all pairs | worst: [('13->46', 2.7), ('44->46', 2.42), ('45->46', 1.93)] | **VIOLATED** |
| C | Guardrail: >=3 of top-5 route 8/66 pairs improve | >=3 pairs < -0.5 | no 8/66 pairs at the Meadowvale harness stop | **UNSCOREABLE** |
| C | Missed-share rule (>0.5 pairs reduce 0.05-0.15) | reduce 0.05-0.15 | 0 scoreable rows | **UNSCOREABLE** |

**Verdict counts:** {'FAIL-LOW': 4, 'FAIL-HIGH': 3, 'PASS': 3, 'UNSCOREABLE': 8, 'FAIL': 1, 'VIOLATED': 1}

**Reconciliation with the emailed 0/4/2/1:** The emailed headline (0 passed / 4 failed / 2 unscoreable / 1 failed low) scored a 7-metric subset with its own unscoreability calls (ghost tooling upgrade, solver re-baseline pending). This mechanical pass scores every pre-reg row it CAN: the good-direction failures (earliness, AM peak, ghosts) reproduce the email's story, as does the bad-direction cluster (after-7pm crowding count). NEW findings: (1) UNSCOPED guardrail violations 13->46 +2.70 and 44->46 +2.42 (the email's scoped reading holds); (2) the catch-all band misses resoundingly in both directions; (3) DIVERGENCE: Route 2 midnight does NOT reproduce the email's 'eased 42->37' on the pre-reg's own period-mean basis (42.5->44.8, worse) — the email used a trip-level readout with no located artifact; the artifact-basis verdict stands per the artifacts-beat-prose rule.

Full detail incl. notes per row: `backtest-sept7-layers-AC.json`.
