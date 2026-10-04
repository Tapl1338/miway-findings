# Verification — every number on the résumé, and how to check it

Each figure below is registered in the project's claim registry with the artifact it comes from and the command that re-derives it. The same registry is enforced on every code change by an automated gate, so a figure cannot drift away from its evidence without a build failing.

Registry as of **2026-10-02** — 16 registered claims.

**Two kinds of evidence, stated plainly.**

* **Publicly checkable** — either the artifact is in this repository, or it is a public web resource (a citable DOI). You can run the command yourself and get the number, right now, with no access to anything private.
* **Requires the instrument** — the figure comes from the running measurement platform (a collector that polls a transit feed around the clock, and the application built on top of it). Those artifacts are not published here, so I am telling you which command re-derives them rather than pretending you could run it.

**Gate status at generation time:** 16/16 claims re-derived from their artifacts.

**Check all of them at once**, in the platform repository:

```bash
python backend/scripts/check_resume_claims.py
```

---

## 1. 6.5M+ unique departures

* **Registry id:** `unique-departures-6-5m-plus`
* **Gate type:** `min` — a floor — the artifact must be **at or above** it
* **Registered value:** `6,500,000`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Unique (date, route_short_name, stop_id, dep_time_min) in the live collector mirror (gitignored obs_lateness.csv; data home). Live re-derive 2026-10-02 (v17.1 floor-bump pass): 6,650,913 unique departures - floor 6.5M holds with headroom 151k; next bump 7M in ~2 collection-days (gate advisory tracks it). History: 4M (mid-Sept) -> 5M (09-22) -> 5.7M (09-27 am) -> 6M (09-27 pm) -> 6.42M at v17 (2026-09-30) -> 6.5M crossed (10-02).

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `(live collector mirror, gitignored)`  
Run from the root of the platform repository:

```bash
python update_departure_floor.py --check   # prints unique departures + floor
```

---

## 2. 4.9M+ APC load observations

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

## 3. 399 on-board check-ins across 14 routes

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

## 4. ~9,700 passenger-minutes per weekday

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

## 5. early departures 62% â†’ 39%, 2.5Ã— the no-school control

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

## 6. ~1-in-60 missed trips pre-change, improving to 1-in-255 after the changeover and holding at 1-in-272 the second week (two consecutive frozen weeks)

* **Registry id:** `ghost-rate-interim`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `272 / 109 / 29605`
* **Gate status when this page was built:** `OK`

**Where it comes from**

docs/findings/findings-v5-sept14-20.md (frozen 2026-09-21): 109 of 29,605 verifiable trips, Sept 14-20 = 1 in 272. Second consecutive frozen week (v4: 121 of 30,848 = 1 in 255). FINAL scorecard receipt exists (docs/runs/sept7-scorecard-verdict-20260922.md, scored 2026-09-22): the interim qualifier requirement is LIFTED â€” 'first week / held second week' wording stays as description, no longer as a hedge.

**Check it yourself — public**

Source: [`docs/findings/findings-v5-sept14-20.md`](findings/findings-v5-sept14-20.md)  
Run from the root of this repository:

```bash
grep -o '\*\*[0-9]* of [0-9,]* verifiable' docs/findings/findings-v5-sept14-20.md
```

*(Same path and same command in the measurement platform's own repository, so it is not repeated here.)*

---

## 7. published as an open dataset (Zenodo, DOI 10.5281/zenodo.22820448)

* **Registry id:** `zenodo-doi-resolves`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `10.5281/zenodo.22820448`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Live DOI resolution (verified 2026-09-20: doi.org -> zenodo.org/records/22820449, deposit contains 3,601,272-row corpus + 250k sample). Network check; CI runs it with a 10s timeout and skips (not fails) on network absence â€” a dead DOI is a manual-page, not a build breaker

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

## 8. 1,300+ backend tests

* **Registry id:** `backend-tests-1300-plus`
* **Gate type:** `min` — a floor — the artifact must be **at or above** it
* **Registered value:** `1,300`
* **Gate status when this page was built:** `OK`

**Where it comes from**

Count of '^def test_' functions under backend/tests: 1,305 (2026-09-23). Floor 1,300 holds with headroom. History: 1,100+ floor -> 1,200 (2026-09-22, live 1,294) -> 1,300 (2026-09-23, live 1,305) after the T158/T159 work landed.

**Re-derivation command — requires the measurement platform**

*This artifact is not published in this repository.*

Source: `backend/tests`  
Run from the root of the platform repository:

```bash
grep -rho '^def test_' backend/tests --include='test_*.py' | wc -l
```

---

## 9. 20 sections spanning lateness, crowding, ghost trips, and equity by ward

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

## 10. winning 100% of 500 simulated days

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

## 11. the optimized plan hid Ward 9 losses (+2.56 min/stop)

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

## 12. backtested the optimizer against the real Sept 7 service change: 5 of 42 pre-registered recommendations matched MiWay's actual re-timing (1 in 6 directional agreement)

* **Registry id:** `backtest-agreement-1-in-6`
* **Gate type:** `exact` — none — the résumé figure must match the artifact exactly
* **Registered value:** `5`
* **Gate status when this page was built:** `OK`

**Where it comes from**

docs/runs/backtest-sept7-matches.json lift_summary.matches = 5 (of 42 scored; near-misses 2 -> 1-in-6 directional; rules pre-registered in backtest-sept7-plan.md)

**Check it yourself — public**

Source: [`docs/runs/backtest-sept7-matches.json`](runs/backtest-sept7-matches.json)  
Run from the root of this repository:

```bash
python -c "import json;n=json.load(open('docs/runs/backtest-sept7-matches.json',encoding='utf-8'))['lift_summary']['matches'];print(n,5<=n<=5 and 'PASS' or 'OUT OF RANGE')"
```

*(Same path and same command in the measurement platform's own repository, so it is not repeated here.)*

---

## 13. predicted route 8's re-timing within 1.9 minutes (announced route; recommended +5.0 min, MiWay shipped +6.91)

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

## 14. Sept 7 was a capacity change, not re-phasing (70 of 84 moved bands changed trip counts)

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

## 15. operated the 24/7 collector at 95.8% SLO coverage in September (23/24 full days)

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

## 16. second standalone collector for Toronto's TTC

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

## How the gate decides

| Type | Meaning | Why some claims use a floor instead of an exact match |
| --- | --- | --- |
| `min` | The résumé states a floor (e.g. “6.5M+ departures”). The artifact must be **at or above** it. | The corpus grows every day the collector runs. An exact match would fail the build every morning — which trains people to ignore red builds. A floor stays true while it is true. |
| `exact` | The résumé figure must equal the artifact value. | Frozen receipts, counts, and strings. Any drift is a real error. |
| `approx` | The résumé figure must be within `tolerance_pct` of the artifact. | Solver nondeterminism and rounding. |

The gate also fails when a registered claim stops appearing on the résumé, and when a **retired** figure reappears — numbers that were once true and are now behind (an earlier test-count floor, a superseded departures floor, my own first, wrong ghost-trip estimate) are on an explicit deny-list.

**12 of 16** claims can be checked from this repository alone. The rest are re-derived by the gate against the platform.

