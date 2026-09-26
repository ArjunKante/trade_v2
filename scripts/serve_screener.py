"""Local web app for browsing the fundamental screener's output --
research tool, single-user, localhost only, no auth, no deployment.

    python scripts/serve_screener.py

Opens the DuckDB warehouse read-only, builds the full in-memory cache once
(momentum universe, screener verdicts, and every top-decile company's full
fundamental_snapshot.py report), then serves it on localhost. Every request
after startup is answered from that cache -- there is no per-request DB
query and no export/copy of the warehouse. Re-run this script after
re-running the screener to pick up new data; there is no auto-refresh.
"""
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import uvicorn

from data_layer.db import get_read_connection
from reports.screener_web import build_cache, create_app

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 8765


def main():
    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
    cache = build_cache(con, progress=lambda msg: print(msg, file=sys.stderr))
    con.close()

    app = create_app(cache)
    url = f"http://{HOST}:{PORT}"
    print(f"\nServing {cache['meta']['n_companies']} companies from the "
          f"{cache['meta']['as_of_date']} screener run ({cache['meta']['log_file'] or 'no log file found'}).")
    print(f"Open {url} in your browser. Ctrl+C to stop.\n")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
