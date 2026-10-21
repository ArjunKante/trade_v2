"""Resolves each identified listing to an Angel One instrument token,
with the Section 3a recovery attempt for symbols Angel's CURRENT
instrument master (a live-only snapshot, `spread_monitor.tokens.
resolve_tokens`, unchanged -- `PREREGISTRATION_IPO.md` Section 0) does
not carry under the listing-day-era symbol.

RECOVERY LOGIC: a symbol rename does not necessarily change the
underlying NSE instrument's Angel token -- Angel's master may simply not
carry the OLD display symbol any more, while still carrying the SAME
instrument under its current one. For each listing whose listing-day
symbol fails to resolve, this chases that company's FULL identity chain
via `isin_lineage` (an existing warehouse table, `data_layer.
isin_lineage`'s own structural ISIN-serial linking, built for exactly
this -- read-only reuse, not duplicated here) -- not just the listing-day
ISIN's own direct history, because some companies change ISIN more than
once (Karda Constructions: INE278R01018 -> ...026 -> ...034, trading as
KARDA throughout, THEN renamed KBCGLOBAL in 2021, THEN DHARAN in 2025 --
all three ISINs share one `isin_lineage` entity_id; a single-hop lookup
from the listing-day ISIN alone would stop at "KARDA" and miss both
later renames). This retrieves every ISIN `isin_lineage` links to the
listing-day ISIN's own entity_id, then the single most-recently-traded
symbol in `prices_eod` across ALL of them, and retries Angel resolution
against THAT symbol. A token found this way is still valid for a
historical `getCandleData` call dated on the original listing day:
Angel's historical candle data is keyed by token, not by whatever symbol
string is currently displayed for it.

A listing that still fails after this retry is recorded as genuinely
unresolved (`NO_TOKEN`) -- never silently dropped.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from spread_monitor.tokens import resolve_tokens


def _latest_symbol_for_isin(con: duckdb.DuckDBPyConnection, isin: str) -> str | None:
    """The single most-recently-traded symbol across every ISIN
    `isin_lineage` links to `isin`'s own entity_id (falls back to just
    `isin` itself if it has no lineage row, e.g. a never-renumbered
    ISIN -- `isin_lineage` only contains rows for ISINs it actually
    decided about, per its own module's documented scope)."""
    linked = con.execute(
        """
        SELECT DISTINCT isin FROM isin_lineage
        WHERE entity_id = (
            SELECT entity_id FROM isin_lineage WHERE isin = ? LIMIT 1
        )
        """,
        [isin],
    ).fetchdf()["isin"].tolist()
    isins = linked or [isin]
    placeholders = ", ".join(["?"] * len(isins))
    row = con.execute(
        f"SELECT symbol FROM prices_eod WHERE isin IN ({placeholders}) ORDER BY trade_date DESC LIMIT 1",
        isins,
    ).fetchone()
    return row[0] if row else None


def resolve_listing_tokens(warehouse_con: duckdb.DuckDBPyConnection, listings: pd.DataFrame) -> pd.DataFrame:
    """`listings`: [listing_id, company_name, listing_date, isin,
    symbol_at_listing] (the `isin` column from `listings.
    attach_listing_day_isin`). Returns the same frame plus [symbol_used,
    token, resolution] where resolution is one of 'direct' (listing-day
    symbol resolved first try), 'recovered' (resolved via the current
    symbol for the same ISIN), or 'unresolved' (NO_TOKEN -- token is
    None)."""
    direct_symbols = listings["symbol_at_listing"].tolist()
    direct_map, direct_missing = resolve_tokens(direct_symbols)

    recovered_map: dict[str, str] = {}
    recovery_symbol_by_listing_symbol: dict[str, str] = {}
    if direct_missing:
        missing_rows = listings[listings["symbol_at_listing"].isin(direct_missing)]
        candidate_current_symbols = []
        for _, r in missing_rows.iterrows():
            cur = _latest_symbol_for_isin(warehouse_con, r["isin"]) if pd.notna(r["isin"]) else None
            if cur and cur != r["symbol_at_listing"]:
                recovery_symbol_by_listing_symbol[r["symbol_at_listing"]] = cur
                candidate_current_symbols.append(cur)
        if candidate_current_symbols:
            recovered_map, _ = resolve_tokens(sorted(set(candidate_current_symbols)))

    rows = []
    for _, r in listings.iterrows():
        sym = r["symbol_at_listing"]
        if sym in direct_map:
            rows.append((sym, direct_map[sym], "direct"))
            continue
        cur_sym = recovery_symbol_by_listing_symbol.get(sym)
        if cur_sym and cur_sym in recovered_map:
            rows.append((cur_sym, recovered_map[cur_sym], "recovered"))
            continue
        rows.append((sym, None, "unresolved"))

    out = listings.copy()
    out["symbol_used"], out["token"], out["resolution"] = zip(*rows)
    return out
