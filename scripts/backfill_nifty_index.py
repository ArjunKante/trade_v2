import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from data_layer.index_nse import backfill_index_range

ROOT = Path(__file__).resolve().parents[1]
con = get_connection(ROOT / "data" / "warehouse.duckdb")
stats = backfill_index_range(con, dt.date(2016, 1, 1), dt.date.today(), ROOT / "data" / "raw" / "index")
print("DONE:", stats)
print(con.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM index_eod").fetchdf().to_string())
con.close()
