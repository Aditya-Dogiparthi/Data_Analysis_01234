# Validation Status

Validation was performed against the supplied synthetic challenge package (seed 42). The full pipeline run ID is `20261030T094553Z`.

| Check | Status | Evidence / note |
|---|---|---|
| Source inventory / raw preservation | PASS | 18 CSV sources inventoried; raw inputs remain unchanged |
| Exact duplicate + key conflict audit | PASS | 2,957 exact duplicates; 14 payment IDs / 28 rows and 79 call IDs / 158 rows quarantined |
| Golden payment reconciliation | PASS | 24,986 conflict-free payment rows; 17,523 SUCCESS events; reversals separate |
| Start-of-month status / denominator policy | PASS WITH LIMITATION | Bitemporal panel generated; observed coverage incomplete; January start status unavailable |
| Agent dimension join cardinality | PASS | 1,000 current agent IDs; agent-call totals reconcile to 89,921 unambiguous calls |
| Full pipeline build | PASS | `python scripts/run_pipeline.py`; run `20261030T094553Z`; 103 generated CSV artifacts hashed |
| Python tests | PASS | `pytest -q`: 23 passed |
| Python syntax | PASS | `python -m compileall -q scripts app tests` |
| YAML parsing | PASS | Docker Compose, dbt project, dbt source and example profile YAML parse |
| Notebook validation | PASS | `notebooks/07_end_to_end_investigation.ipynb`: 28 cells, executed with zero cell errors |
| Dashboard Python syntax | PASS | Included in compileall; Streamlit runtime launch not tested |
| Dashboard launch | NOT RUN HERE | `streamlit` is not installed in this build environment; install `requirements.txt` and run `streamlit run app/dashboard.py` locally |
| PostgreSQL integration | NOT RUN HERE | Requires Docker/PostgreSQL service and database credentials |
| dbt parse/run/test | NOT RUN HERE | `dbt` is not installed/configured in this build environment |
| PostgreSQL SQL execution | NOT RUN HERE | SQL is PostgreSQL 16-targeted; no live database connection in this build environment |
| GitHub push | NOT RUN | Requires the user's repository and credentials |

Do not represent an unrun integration check as passed. Re-run the local verification commands in `README.md` after installing/configuring the optional services.
