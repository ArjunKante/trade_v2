# NSE Factor & Fundamentals System — Phase 1 (Data Layer)

Status: Phase 1 gate. See `LICENSE_ASSESSMENT.md` for the source-by-source
licensing decision. See `PREREGISTRATION.md` (to be written before any model
runs, per project rules) for locked design choices once Phase 6 is reached.

## Layout
```
config/config.yaml           source URLs, throttles, universe definition
src/data_layer/
  db.py                      DuckDB schema + as_of query guard (HoldoutViolationError)
  prices_nse.py              NSE bhavcopy (UDiFF) fetch + parse + load
  fundamentals_nse.py        NSE-hosted XBRL financial-results fetch + load
  xbrl_parser.py             long-format XBRL fact extraction
scripts/phase1_demo_load.py  one-off driver proving the pipeline against real data
tests/test_known_date_guard.py  unit tests for the known_date <= as_of invariant
data/warehouse.duckdb        the point-in-time warehouse (append-only)
data/raw/                    cached raw files (bhavcopy zips, XBRL XML)
```

## Running
```
pip install -r requirements.txt
python scripts/phase1_demo_load.py
python -m pytest tests/ -v
```
