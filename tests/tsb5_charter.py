"""T-SB5 stress charter — five builders, one lane, real bounded tasks.

Each builder i (1..5) implements backend/scripts/hub_stats_<i>.py against the
shared acceptance gate backend/tests/test_tsb5_hub_stats.py (pre-written).
The gate imports the module named by env var HUB_STATS_MODULE, so all five
builders share one contract but produce independent files. Each charter file
says exactly what to build. DONE-WHEN: the gate passes for that builder.
"""

# Per-builder module matrix: the contract is identical; only the module name
# differs. The gate reads HUB_STATS_MODULE to pick the file under test.

CONTRACT = """
Contract (all five identical except module name):
- module backend/scripts/hub_stats_<i>.py, pure stdlib (csv module only, NO pandas)
- load_stops(csv_path) -> list[dict]: rows as parsed; 'boardings' as int;
  stop_id stays a string (leading zeros preserved, e.g. "0427")
- total_boardings(rows) -> int (0 for empty)
- top_stops(rows, n=5) -> list[dict]: highest boardings first; ties broken by
  stop_id ascending as an INTEGER (e.g. "902" before "1103")
- worst_stops(rows, n=3) -> list[dict]: lowest boardings first, same tie-break
- summary(rows) -> {"total": int, "stops_count": int, "top": [stop_id, ...]}
  where top is the top-5 stop_ids (or fewer if fewer stops)
- n <= 0 in top_stops/worst_stops returns []
"""

TASKS = {
    1: "Implement backend/scripts/hub_stats_1.py per the contract below.",
    2: "Implement backend/scripts/hub_stats_2.py per the contract below.",
    3: "Implement backend/scripts/hub_stats_3.py per the contract below.",
    4: "Implement backend/scripts/hub_stats_4.py per the contract below.",
    5: "Implement backend/scripts/hub_stats_5.py per the contract below.",
}

# CSV fixture written into each worktree by the launcher; the gate writes its
# own fixtures via tmp_path, so builders need no live data file.
SAMPLE_CSV = """stop_id,stop_name,boardings
1103,City Centre,4100
0427,Meadowvale,2700
902,Sheridan,4100
315,Dundas,1000
6671,Lakeshore,850
0119,Erin Mills,500
"""


def charter_for(i: int) -> str:
    return (
        f"T-SB5 BUILDER {i}\n\n"
        f"{TASKS[i]}\n\n"
        "Acceptance gate (pre-written, DO NOT MODIFY): "
        "backend/tests/test_tsb5_hub_stats.py\n"
        "Run it with HUB_STATS_MODULE set to your module name:\n\n"
        "    cd backend && set HUB_STATS_MODULE=hub_stats_" + str(i) + " && "
        "python -m pytest tests/test_tsb5_hub_stats.py -v\n"
        "    (bash: HUB_STATS_MODULE=hub_stats_" + str(i) + " python -m pytest ...)\n\n"
        f"{CONTRACT}\n"
        "Rules:\n"
        "- Create ONLY backend/scripts/hub_stats_" + str(i) + ".py.\n"
        "- Do NOT modify the test file, other builders' files, or anything else.\n"
        "- DONE-WHEN: the gate passes with exit 0.\n"
        "- A sample CSV fixture exists at backend/tests/fixtures/hub_stats_sample.csv "
        "if you want to eyeball the data shape.\n"
    )
