# Verification — every number on the résumé, and how to check it

Each figure below is registered in the project's claim registry with the artifact it comes from and the command that re-derives it. The same registry is enforced on every code change by an automated gate, so a figure cannot drift away from its evidence without a build failing.

Registry as of **2026-10-17** — 27 registered claims.

**Two kinds of evidence, stated plainly.**

* **Publicly checkable** — either the artifact is in this repository, or it is a public web resource (a citable DOI). You can run the command yourself and get the number, right now, with no access to anything private.
* **Requires the instrument** — the figure comes from the running measurement platform (a collector that polls a transit feed around the clock, and the application built on top of it). Those artifacts are not published here, so I am telling you which command re-derives them rather than pretending you could run it.

**Gate status at generation time:** 27/27 claims re-derived from their artifacts.

**Check all of them at once**, in the platform repository:

```bash
python backend/scripts/check_resume_claims.py
```

---

## 1. a feed 7× MiWay's size (249,592 vs 34,092 weekly trips)

* **Registry id:** `ttc-feed-size-7x`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `yes`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Re-derived 2026-10-05 by backend/scripts/measure_feed_size.py (v2: streaming; MiWay via app.gtfs_kit.service_ids_on; TTC from Toronto open-data SurfaceGTFS, the same URL collect_ttc.py downloads; calendar_dates.txt exceptions resolved PER DATE). Representative Mon-Sun week 2026-10-19..25 (deliberately not the Thanksgiving week): MiWay 34,092 weekly trips / 67 routes / 4,085 stops; TTC 249,592 weekly trips / 225 routes / 9,101 stops → 7.32×. CORRECTION HISTORY — two earlier figures were wrong and both came from a script bug, not the feed: v1 read calendar.txt day-flags but never calendar_dates.txt, so it applied Thanksgiving service (service 2, 30,379 trips) to 2026-10-05, a Monday on which that service is explicitly REMOVED. That produced a phantom Monday of 68,054 and hence 12.18× (weekday avg) and 8.21× (weekly). Resolved per date, every Monday in the TTC window is 37,675 except Thanksgiving 2026-10-12 at 30,379 - Monday is NOT special. DO NOT re-derive from day-flags alone; that reproduces the wrong numbers. Frozen receipt: docs/runs/feed-size-receipt-20261005.md (v2).

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `docs/runs/feed-size-receipt-20261005.md`  
Run from the root of the platform repository:

```bash
grep -nE '249,592|34,092|7\.32×|Why\ two\ earlier\ figures\ were\ wrong\ —\ read\ before\ re\-deriving' docs/runs/feed-size-receipt-20261005.md
```

---

## 2. 9M+ unique departures

* **Registry id:** `unique-departures-9m-plus`
* **Gate type:** `min` — a floor — the artifact must be **at or above** it
* **Registered value:** `9,000,000`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Unique (date, route_short_name, stop_id, dep_time_min) in the live collector mirror (gitignored obs_lateness.csv; data home). Live re-derive 2026-10-17 (floor-bump pass; gate advisory reported 9,008,463 against the old 6.5M floor, 3.5M behind): floor 9M holds; the +0.5M cadence makes 9.5M the next bump, not an immediate one (re-derive before quoting: this corpus grows ~185k unique tuples per weekday). History: 4M (mid-Sept) -> 5M (09-22) -> 5.7M (09-27 am) -> 6M (09-27 pm) -> 6.42M at v17 (2026-09-30) -> 6.5M crossed (10-02) -> 9M crossed (mid-Oct; re-derived 9,008,463 on 10-17).

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `(live collector mirror, gitignored)`  
Run from the root of the platform repository:

```bash
python update_departure_floor.py --check   # prints unique departures + floor
```

---

## 3. 4.9M+ APC load observations

* **Registry id:** `apc-observations-4-9m-plus`
* **Gate type:** `min` — a floor — the artifact must be **at or above** it
* **Registered value:** `4,900,000`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Sum of n_observations in backend/app/data/occupancy_stats.csv (verified 4,990,668 on 2026-09-18; frozen artifact, stable)

**Check it yourself — public**

Source: [`data/occupancy_stats.csv`](../data/occupancy_stats.csv)  
Run from the root of this repository:

```bash
python -c "import csv;print(sum(int(float(r['n_observations'])) for r in csv.DictReader(open('data/occupancy_stats.csv',newline='',encoding='utf-8'))))"
```

**Re-derivation command — requires the measurement platform**

Source: `backend/app/data/occupancy_stats.csv`  
Run from the root of the platform repository:

```bash
python -c "import csv;print(sum(int(float(r['n_observations'])) for r in csv.DictReader(open('backend/app/data/occupancy_stats.csv',newline='',encoding='utf-8'))))"
```

---

## 4. 399 on-board check-ins across 14 routes

* **Registry id:** `apc-checkins-399-routes-14`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `399 / 14`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Row count and distinct route count of backend/app/data/ground_truth.csv (verified 399 / 14 on 2026-09-20; frozen audit artifact)

**Check it yourself — public**

Source: [`data/ground_truth.csv`](../data/ground_truth.csv)  
Run from the root of this repository:

```bash
python -c "import csv;rs=list(csv.DictReader(open('data/ground_truth.csv',newline='',encoding='utf-8')));ks={r.get('route_short_name') or r.get('route','') for r in rs}-{''};print(len(rs),'check-ins across',len(ks),'routes')"
```

**Re-derivation command — requires the measurement platform**

Source: `backend/app/data/ground_truth.csv`  
Run from the root of the platform repository:

```bash
python -c "import csv;rs=list(csv.DictReader(open('backend/app/data/ground_truth.csv',newline='',encoding='utf-8')));ks={r.get('route_short_name') or r.get('route','') for r in rs}-{''};print(len(rs),'check-ins across',len(ks),'routes')"
```

---

## 5. ~9,700 passenger-minutes per weekday

* **Registry id:** `optimizer-saved-pax-minutes`
* **Gate type:** `approx` — ±5% — the résumé figure must be within this of the artifact
* **Registered value:** `9,700`
* **Gate status when this page was built:** `OK`

**Where it comes from**

docs/exec-summary.json result.saved_pax_minutes (9,714.6 at basis miss_model=july, 20260911). NOTE: per check_readme_headline.py, this headline must cite the miss model; the resume's 'modeled ... reported conservatively' phrasing is the approved form

**Check it yourself — public**

Source: [`data/exec-summary.json`](../data/exec-summary.json)  
Run from the root of this repository:

```bash
python -c "import json;print(json.load(open('data/exec-summary.json',encoding='utf-8'))['result']['saved_pax_minutes'])"
```

**Re-derivation command — requires the measurement platform**

Source: `docs/exec-summary.json`  
Run from the root of the platform repository:

```bash
python -c "import json;print(json.load(open('docs/exec-summary.json',encoding='utf-8'))['result']['saved_pax_minutes'])"
```

---

## 6. early departures 62.3% → 38.9%, 2.5× the no-school control

* **Registry id:** `retime-school-stop-win`
* **Gate type:** `exact` — ±1% — the résumé figure must be within this of the artifact
* **Registered value:** `62.3 / 38.9 / 2.5`
* **Gate status when this page was built:** `OK`

**Where it comes from**

docs/findings/school-stop-retime-win.md frozen receipt: school-door 62.3% (n=970) -> 38.9% (n=496), control -9.5pp; 23.4pp / 9.5pp = 2.46x ~ 2.5x (frozen presented window)

**Check it yourself — public**

Source: [`docs/findings/school-stop-retime-win.md`](findings/school-stop-retime-win.md)  
Run from the root of this repository:

```bash
grep -n '62\.3%\|38\.9%\|9\.5 pp' docs/findings/school-stop-retime-win.md
```

*(Same path and same command in the measurement platform's own repository, so it is not repeated here.)*

---

## 7. ~1-in-60 missed trips pre-change, improving to 1-in-255 after the changeover and holding at 1-in-272 the second week (two consecutive frozen weeks)

* **Registry id:** `ghost-rate-interim`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `272 / 109 / 29605`
* **Gate status when this page was built:** `OK`

**Where it comes from**

docs/findings/findings-v5-sept14-20.md (frozen 2026-09-21): 109 of 29,605 verifiable trips, Sept 14-20 = 1 in 272. Second consecutive frozen week (v4: 121 of 30,848 = 1 in 255). FINAL scorecard receipt exists (docs/runs/sept7-scorecard-verdict-20260922.md, scored 2026-09-22): the interim qualifier requirement is LIFTED — 'first week / held second week' wording stays as description, no longer as a hedge.

**Check it yourself — public**

Source: [`docs/findings/findings-v5-sept14-20.md`](findings/findings-v5-sept14-20.md)  
Run from the root of this repository:

```bash
grep -o '\*\*[0-9]* of [0-9,]* verifiable' docs/findings/findings-v5-sept14-20.md
```

*(Same path and same command in the measurement platform's own repository, so it is not repeated here.)*

---

## 8. published as an open dataset (Zenodo, DOI 10.5281/zenodo.22820448)

* **Registry id:** `zenodo-doi-resolves`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `10.5281/zenodo.22820448`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Live DOI resolution (verified 2026-09-20: doi.org -> zenodo.org/records/22820449, deposit contains 3,601,272-row corpus + 250k sample). Network check; CI runs it with a 10s timeout and skips (not fails) on network absence — a dead DOI is a manual-page, not a build breaker

**Check it yourself — public**

Source: [https://doi.org/10.5281/zenodo.22820448](https://doi.org/10.5281/zenodo.22820448) — anyone with a network connection can run this.  
Run anywhere:

```bash
curl -sIL -o /dev/null -w '%{url_effective} %{http_code}\n' https://doi.org/10.5281/zenodo.22820448
```

**Re-derivation command — requires the measurement platform**

Source: `https://doi.org/10.5281/zenodo.22820448`  
Run from the root of the platform repository:

```bash
curl -sIL -o /dev/null -w '%{url_effective} %{http_code}\n' https://doi.org/10.5281/zenodo.22820448
```

---

## 9. 1,400+ backend tests

* **Registry id:** `backend-tests-1300-plus`
* **Gate type:** `min` — a floor — the artifact must be **at or above** it
* **Registered value:** `1,400`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Count of '^def test_' functions under backend/tests: 1,447 (2026-10-03). Floor 1,400 holds with headroom. History: 1,100+ floor -> 1,200 (2026-09-22) -> 1,300 (2026-09-23, live 1,305) -> 1,400 (2026-10-03, live 1,447)

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `backend/tests`  
Run from the root of the platform repository:

```bash
grep -rho '^def test_' backend/tests --include='test_*.py' | wc -l
```

---

## 10. 20 sections spanning lateness, crowding, ghost trips, and equity by ward

* **Registry id:** `ui-sections-20`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `20`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Sections in the SHELLS array of frontend/src/lib/viewConfig.ts (v1.1 five-view consolidation, T158): 20 section keys across 5 shells. Verifier counts 'key: '' entries in the SHELLS block only (stops at ALL_SECTIONS/LEGACY_VIEW_MAP so legacy keys never count). History: '18 dashboards' (VIEWS array, pre-T158) -> '20 sections' (2026-09-23).

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `frontend/src/lib/viewConfig.ts`  
Run from the root of the platform repository:

```bash
sed -n '/export const SHELLS/,/ALL_SECTIONS/p' frontend/src/lib/viewConfig.ts | grep -o "key: '[a-z-]*'" | sort -u | wc -l
```

---

## 11. winning 100% of 500 simulated days

* **Registry id:** `optimizer-500-days`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `100 / 500`
* **Gate status when this page was built:** `OK`

**Where it comes from**

docs/runs/FQ8-montecarlo-verdict-20260830.md frozen verdict (500/500 simulated days; NEVER quote the banned 74%/50-day fossil)

**Check it yourself — public**

Source: [`docs/runs/FQ8-montecarlo-verdict-20260830.md`](runs/FQ8-montecarlo-verdict-20260830.md)  
Run from the root of this repository:

```bash
grep -n '500\|100%' docs/runs/FQ8-montecarlo-verdict-20260830.md
```

*(Same path and same command in the measurement platform's own repository, so it is not repeated here.)*

---

## 12. the optimized plan hid Ward 9 losses (+2.56 min/stop)

* **Registry id:** `ward9-equity-loss`
* **Gate type:** `approx` — ±1% — the résumé figure must be within this of the artifact
* **Registered value:** `2.56`
* **Gate status when this page was built:** `OK`

**Where it comes from**

docs/equity-report.json wards.rows[ward=='9'].delta_minutes (2.56, 21 stops, 15 worse-off; DEC-07 corrected vintage per RUN-OF-RECORD:33)

**Check it yourself — public**

Source: [`demo/api-snapshot/equity-report.json`](../demo/api-snapshot/equity-report.json)  
Run from the root of this repository:

```bash
python -c "import json;d=json.load(open('demo/api-snapshot/equity-report.json',encoding='utf-8'));r=[x for x in d['wards']['rows'] if x['ward']=='9'][0];print(r['delta_minutes'])"
```

**Re-derivation command — requires the measurement platform**

Source: `docs/equity-report.json`  
Run from the root of the platform repository:

```bash
python -c "import json;d=json.load(open('docs/equity-report.json',encoding='utf-8'));r=[x for x in d['wards']['rows'] if x['ward']=='9'][0];print(r['delta_minutes'])"
```

---

## 13. backtested the optimizer against the real Sept 7 service change under pre-registered rules: 5 of 42 scored routes matched within ±3 min (11.9%); 7 of 42 (16.7%) agreed on direction

* **Registry id:** `backtest-agreement-1-in-6`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `5`
* **Gate status when this page was built:** `OK`

**Where it comes from**

docs/runs/backtest-sept7-matches.json lift_summary.matches = 5 of scored_recommendations 42 (hit_rate 0.119); near_misses 2 -> 7 of 42 = 16.7% same-direction (rules pre-registered in backtest-sept7-plan.md). Both halves of the sentence are registered separately so neither can be dropped unnoticed.

**Check it yourself — public**

Source: [`docs/runs/backtest-sept7-matches.json`](runs/backtest-sept7-matches.json)  
Run from the root of this repository:

```bash
python -c "import json;n=json.load(open('docs/runs/backtest-sept7-matches.json',encoding='utf-8'))['lift_summary']['matches'];print(n,5<=n<=5 and 'PASS' or 'OUT OF RANGE')"
```

*(Same path and same command in the measurement platform's own repository, so it is not repeated here.)*

---

## 14. 5 of 42 pre-registered recommendations matched within ±3 min (11.9%)

* **Registry id:** `backtest-hit-rate-11-9-pct`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `0.119`
* **Gate status when this page was built:** `OK`

**Where it comes from**

docs/runs/backtest-sept7-matches.json lift_summary.hit_rate = 0.119 (5 matches / 42 scored)

**Check it yourself — public**

Source: [`docs/runs/backtest-sept7-matches.json`](runs/backtest-sept7-matches.json)  
Run from the root of this repository:

```bash
python -c "import json;n=json.load(open('docs/runs/backtest-sept7-matches.json',encoding='utf-8'))['lift_summary']['hit_rate'];print(n,0.119<=n<=0.119 and 'PASS' or 'OUT OF RANGE')"
```

*(Same path and same command in the measurement platform's own repository, so it is not repeated here.)*

---

## 15. 7 of 42 (16.7%) agreed on direction — the 5 strict matches PLUS 2 near-misses (same sign, off magnitude)

* **Registry id:** `backtest-directional-16-7-pct`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `2`
* **Gate status when this page was built:** `OK`

**Where it comes from**

docs/runs/backtest-sept7-matches.json lift_summary.near_misses = 2; 5 matches + 2 near-misses = 7 of 42 = 16.7% same-direction (docs/exhibits/backtest-sept7-onepager.md)

**Check it yourself — public**

Source: [`docs/runs/backtest-sept7-matches.json`](runs/backtest-sept7-matches.json)  
Run from the root of this repository:

```bash
python -c "import json;n=json.load(open('docs/runs/backtest-sept7-matches.json',encoding='utf-8'))['lift_summary']['near_misses'];print(n,2<=n<=2 and 'PASS' or 'OUT OF RANGE')"
```

*(Same path and same command in the measurement platform's own repository, so it is not repeated here.)*

---

## 16. predicted route 8's re-timing within 1.9 minutes (announced route; recommended +5.0 min, MiWay shipped +6.91)

* **Registry id:** `backtest-route8-within-2-min`
* **Gate type:** `approx` — ±40% — the résumé figure must be within this of the artifact
* **Registered value:** `6.91`
* **Gate status when this page was built:** `OK`

**Where it comes from**

docs/runs/backtest-sept7-actual-change.json rows[route=='8',band=='am_rush'].delta_dep = 6.91 (recommended +5.0 -> within 1.9 min; wide tolerance: agency's own re-timing is not a stable constant)

**Check it yourself — public**

Source: [`docs/runs/backtest-sept7-actual-change.json`](runs/backtest-sept7-actual-change.json)  
Run from the root of this repository:

```bash
python -c "import json;d=json.load(open('docs/runs/backtest-sept7-actual-change.json',encoding='utf-8'));print([x for x in d['rows'] if x['route']=='8' and x['band']=='am_rush'][0]['delta_dep'])"
```

*(Same path and same command in the measurement platform's own repository, so it is not repeated here.)*

---

## 17. Sept 7 was a capacity change, not re-phasing (70 of 84 moved bands changed trip counts)

* **Registry id:** `backtest-capacity-not-rephase`
* **Gate type:** `exact` — ±5% — the résumé figure must be within this of the artifact
* **Registered value:** `70`
* **Gate status when this page was built:** `OK`

**Where it comes from**

docs/runs/backtest-sept7-actual-change.json summary.frequency_changed_of_moved = 70 (of 84 moved bands)

**Check it yourself — public**

Source: [`docs/runs/backtest-sept7-actual-change.json`](runs/backtest-sept7-actual-change.json)  
Run from the root of this repository:

```bash
python -c "import json;n=json.load(open('docs/runs/backtest-sept7-actual-change.json',encoding='utf-8'))['summary']['frequency_changed_of_moved'];print(n,70<=n<=70 and 'PASS' or 'OUT OF RANGE')"
```

*(Same path and same command in the measurement platform's own repository, so it is not repeated here.)*

---

## 18. operated the 24/7 collector at 95.8% SLO coverage in September (23/24 full days)

* **Registry id:** `uptime-slo-95pct`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `yes`
* **Gate status when this page was built:** `OK`

**Where it comes from**

docs/runs/uptime-2026-09.md frozen report must contain the coverage line (95.8%, 23/24 FULL days); re-derivable via scripts/uptime_report.py --month 2026-09

**Check it yourself — public**

Source: [`docs/runs/uptime-2026-09.md`](runs/uptime-2026-09.md)  
Run from the root of this repository:

```bash
grep -nE '95\.8%|23/24\ FULL\ days' docs/runs/uptime-2026-09.md
```

*(Same path and same command in the measurement platform's own repository, so it is not repeated here.)*

---

## 19. second standalone collector for Toronto's TTC

* **Registry id:** `ttc-second-collector`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `yes`
* **Gate status when this page was built:** `OK`

**Where it comes from**

backend/scripts/collect_ttc.py exists; acceptance gates in docs/runs/ttc-collector-cadence-receipt-20260928.md: 100% poll success, unmatched 15-17% vs 50% cap (two live cadence runs, 2026-09-28). Hands-off confirmed 2026-09-29 (deploy card).

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `backend/scripts/collect_ttc.py`  
Run from the root of the platform repository:

```bash
test -f backend/scripts/collect_ttc.py && echo present
```

---

## 20. 30M+ observations logged by the second, standalone collector mirroring the measurement on Toronto's TTC surface network (since 2026-09-28)

* **Registry id:** `ttc-observations-30m-plus`
* **Gate type:** `min` — a floor — the artifact must be **at or above** it
* **Registered value:** `30,000,000`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Sum of the resolved per-day `obs` counter over <data-home>/ttc/day-*.json, read through app/ttc_counters.py (the ONE owner of those semantics): 36,071,653 as of 2026-10-14 across 17 day files (36,068,512 an hour earlier - the collector is live, which is exactly why this is a floor and not an exact figure). A LOWER BOUND by construction: 2026-09-28 has no preceding day file (unresolvable, never counted as zero) and 2026-09-30 / 10-01 / 10-02 / 10-03 are restart days (box 2's deployment window, its counters resetting), so each reports only the count since its restart. Construct is observations LOGGED - rows appended per poll, every horizon the feed carried - NOT the deduped unique-departure count the MiWay claim uses; a unique-departure analogue needs a memory-bounded external sort over the 666 MB mirror and has NOT been run. Kept a SEPARATE claim from the MiWay counter by owner decision 2026-10-02 (no coherent combined basis). Registered ahead of its resume line on purpose - the scholarship-application gate opened 2026-10-13 - so it carries no RESUME_PATTERNS entry and the gate does not require it in a resume until a variant adopts this wording.

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `(live collector mirror, gitignored)`  
Run from the root of the platform repository:

```bash
python -c "import json,subprocess;out=subprocess.run(['python','backend/scripts/check_resume_claims.py','--json','--skip-network'],capture_output=True,text=True).stdout;print([r['detail'] for r in json.loads(out)['results'] if r['id'] == 'ttc-observations-30m-plus'][0])"
```

---

## 21. the Ward 9 councillor's office referred the findings to MiWay staff twice (2026-08-26 and 2026-09-24)

* **Registry id:** `councillor-referral-receipted`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `yes`
* **Gate status when this page was built:** `OK`

**Where it comes from**

docs/runs/councillor-referral-receipt-20261004.md frozen receipt: quotes both office replies (request sent to MiWay for investigation, 2026-08-26; email shared with MiWay staff, 2026-09-24). The full thread with personal contact details stays OFF-repo as docs/uni/evidence-councillor-referral.pdf (SHA-256 recorded in the receipt). Note: previously prose-corroborated only; this entry closes that gap. NOT yet required_in_all_resumes — becomes required when a resume version adopts the referral line with this exact scoping.

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `docs/runs/councillor-referral-receipt-20261004.md`  
Run from the root of the platform repository:

```bash
grep -nE 'request\ will\ be\ sent\ to\ MiWay\ for\ investigation|shared\ your\ email\ with\ MiWay\ staff' docs/runs/councillor-referral-receipt-20261004.md
```

---

## 22. 60 personalized cold emails to research labs (send window 2026-06-22 to 2026-07-08)

* **Registry id:** `outreach-60-emails`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `yes`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Re-derived from the 60 archived cold-outreach Gmail threads by backend/scripts/outreach_evidence_report.py (needs pymupdf: system Python312, not the CI venv). The reply counts are not prose: docs/runs/outreach-evidence-ledger-20261005.csv (per-thread SHA-256 + counts; raw threads stay OFF-repo under docs/uni/emails/ per the 2026-09-30 owner decision). Auto-reply scan over all 60 threads returns 0 hits, so every reply counted is human. NOT required_in_all_resumes — the v20 resume files do not all carry the outreach line; becomes required when a resume version adopts it with this exact scoping. 60 campaign threads (subject matches an outreach template), one first-touch each; 90 messages total including follow-ups. Registry wording: 60 cold emails sent. NOTE on resume_value: it is the boolean true, not the figure, because the json_exists verifier returns a bool; the numeric assertion is carried by the `contains` strings below and by docs/runs/outreach-evidence-ledger-20261005.csv. Do not "fix" this back to a bare number — that is what broke the first gate run.

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `docs/runs/outreach-evidence-receipt-20261005.md`  
Run from the root of the platform repository:

```bash
grep -nE 'Cold\-outreach\ emails\ sent|60\ campaign\ threads|Send\ window' docs/runs/outreach-evidence-receipt-20261005.md
```

---

## 23. 26 of the 60 outreach emails drew a reply (28 reply messages in 26 threads)

* **Registry id:** `outreach-26-replies`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `yes`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Re-derived from the 60 archived cold-outreach Gmail threads by backend/scripts/outreach_evidence_report.py (needs pymupdf: system Python312, not the CI venv). The reply counts are not prose: docs/runs/outreach-evidence-ledger-20261005.csv (per-thread SHA-256 + counts; raw threads stay OFF-repo under docs/uni/emails/ per the 2026-09-30 owner decision). Auto-reply scan over all 60 threads returns 0 hits, so every reply counted is human. NOT required_in_all_resumes — the v20 resume files do not all carry the outreach line; becomes required when a resume version adopts it with this exact scoping. Two threads carry a second reply (brown, johnson mac). The 26 is the thread count, which is what the claim means. Registry wording: 26 threads replied. NOTE on resume_value: it is the boolean true, not the figure, because the json_exists verifier returns a bool; the numeric assertion is carried by the `contains` strings below and by docs/runs/outreach-evidence-ledger-20261005.csv. Do not "fix" this back to a bare number — that is what broke the first gate run.

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `docs/runs/outreach-evidence-receipt-20261005.md`  
Run from the root of the platform repository:

```bash
grep -nE 'Threads\ with\ >=\ 1\ reply|26\ of\ 60\ =\ 43%|Auto\-replies\ among\ them|Reply\ digest\ —\ all\ 26\ replying\ threads|Zero\ summer\-2026\ placements' docs/runs/outreach-evidence-receipt-20261005.md
```

---

## 24. a same-day endorsement from a U of T professor

* **Registry id:** `outreach-brown-endorsement`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `yes`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Quoted verbatim in docs/runs/outreach-evidence-receipt-20261005.md: An assistant professor at U of T's Leslie Dan Faculty of Pharmacy replied 2026-06-26 15:39, 3 h 38 min after the 12:01 send: 'your message is right on the mark and convincing!'. Same calendar day, so 'same-day' holds.

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `docs/runs/outreach-evidence-receipt-20261005.md`  
Run from the root of the platform repository:

```bash
grep -nE 'your\ message\ is\ right\ on\ the\ mark\ and\ convincing!|Same\-day\ endorsement\ from\ a\ U\ of\ T\ professor' docs/runs/outreach-evidence-receipt-20261005.md
```

---

## 25. a lab tour offer

* **Registry id:** `outreach-lab-tour-offer`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `yes`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Quoted verbatim in docs/runs/outreach-evidence-receipt-20261005.md: A U of T biochemistry professor and graduate coordinator, 2026-06-30 11:12: 'we do not have volunteer students in our BSL2 lab. If you have time in August, we can invite you to visit the lab for a tour'. The recipient ACCEPTED it in writing on 2026-07-02 ('I would love to take you up on your offer for a lab tour this August'), but the professor never replied again, so no date was scheduled and there is no evidence the tour happened. SCOPE: keep the claim an OFFER (accepted, unscheduled). Must not become 'a lab tour'/'visited the lab'/'toured a U of T lab' without a new artifact.

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `docs/runs/outreach-evidence-receipt-20261005.md`  
Run from the root of the platform repository:

```bash
grep -nE 'we\ can\ invite\ you\ to|never\ replied|no\ date\ was\ ever\ scheduled' docs/runs/outreach-evidence-receipt-20261005.md
```

---

## 26. an offer to arrange summer 2027 research (v21 wording; v20 said "a confirmed research placement")

* **Registry id:** `outreach-summer-2027-placement`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `yes`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Quoted verbatim in docs/runs/outreach-evidence-receipt-20261005.md: The same pharmacy professor, 2026-06-28 17:19: 'All sounds good and yes, we can set something up next year. Reach out in March next spring.' SCOPE: an agreement in principle for summer 2027 with a re-contact condition, from a lab founded January 2026 — NOT a signed placement, offer letter or start date. Summer 2027 is the correct year (the June 2026 conversation's 'next summer'). WORDING HISTORY (2026-10-05): resume v21 deliberately weakened the resume line from 'a confirmed research placement for summer 2027' to 'an offer to arrange summer 2027 research', matching this receipt's scope. THIS registry entry now tracks the v21 wording. The v20 build still says 'confirmed research placement' and v20 is what was SENT to the referee on 2026-10-05 — do not retro-edit the sent PDF, and do NOT 'restore' the stronger wording into v21: the evidence supports the weaker claim.

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `docs/runs/outreach-evidence-receipt-20261005.md`  
Run from the root of the platform repository:

```bash
grep -nE 'we\ can\ set\ something\ up\ next\ year|\*\*not\*\*\ a\ signed\ placement|"restore"\ the\ stronger\ phrasing' docs/runs/outreach-evidence-receipt-20261005.md
```

---

## 27. referrals to two university programs (both from one thread)

* **Registry id:** `outreach-two-program-referrals`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `yes`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Quoted verbatim in docs/runs/outreach-evidence-receipt-20261005.md: The same pharmacy professor, 2026-06-28, referred exactly two in that one message — the STEM Fellowship Research Experience Opportunity (stemfellowship.org/reo) and the U of T Faculty of Pharmacy CPD camp (cpd.pharmacy.utoronto.ca/pages/camp). SCOPE (widened 2026-10-05 after reading all 28 reply bodies): 'two' is THAT PROFESSOR'S TWO FROM ONE THREAD, not the campaign-wide total. The campaign produced FOUR program pointers to three distinct programs — the pharmacy professor x2, plus another researcher independently recommending the same STEM Fellowship REO (2026-07-08), plus the LTRI program a third researcher named while declining. The earlier ledger tally '2 + 1' undercounted by one. The claim is accurate as written (it does not claim a campaign total); do NOT cite 'two' as the campaign-wide figure, and do not read the full inventory as 'four referrals' — two of them are the same REO program. NOTE on resume_value: it is the boolean true, not the figure, because the json_exists verifier returns a bool; the numeric assertion is carried by the `contains` strings below and by docs/runs/outreach-evidence-ledger-20261005.csv. Do not "fix" this back to a bare number — that is what broke the first gate run.

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `docs/runs/outreach-evidence-receipt-20261005.md`  
Run from the root of the platform repository:

```bash
grep -nE 'stemfellowship\.org/reo|cpd\.pharmacy\.utoronto\.ca/pages/camp|Campaign\-wide\ program\ pointers:\ four\ pointers\ to\ three\ distinct\ programs' docs/runs/outreach-evidence-receipt-20261005.md
```

---

## How the gate decides

| Type | Meaning | Why some claims use a floor instead of an exact match |
| --- | --- | --- |
| `min` | The résumé states a floor (e.g. “9M+ departures”). The artifact must be **at or above** it. | The corpus grows every day the collector runs. An exact match would fail the build every morning — which trains people to ignore red builds. A floor stays true while it is true. |
| `exact` | The résumé figure must equal the artifact value. | Frozen receipts, counts, and strings. Any drift is a real error. |
| `approx` | The résumé figure must be within `tolerance_pct` of the artifact. | Solver nondeterminism and rounding. |

The gate also fails when a registered claim stops appearing on the résumé, and when a **retired** figure reappears — numbers that were once true and are now behind (an earlier test-count floor, a superseded departures floor, my own first, wrong ghost-trip estimate) are on an explicit deny-list.

**14 of 27** claims can be checked from this repository alone. The rest are re-derived by the gate against the platform.

