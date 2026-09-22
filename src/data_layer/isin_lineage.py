"""ISIN lineage resolution: links same-company ISIN changes into one entity_id
without ever rewriting prices_eod (which stays keyed on bare ISIN, permanently).

Indian ISINs are structured, not opaque (NSDL allocation, 12 chars):

    I  N  E  2  9  6  A  0  1  0  2  4
    [country+class][ issuer (4) ][type(2)][serial(2)][check]

NSDL reissues a new ISIN under the SAME issuer+type on certain corporate
actions (face-value changes, restructuring) while the underlying company and
security class are unchanged. Confirmed against two real, independently
verified examples: Kotak Mahindra Bank (INE237A01028 -> INE237A01036, issuer
237A both, serial 02->03) and BAJFINANCE (INE296A01016 -> INE296A01024 ->
INE296A01032, issuer 296A throughout, serial 01->02->03).

This structural match is treated as PRIMARY evidence -- deterministic, not
inferred -- and is a hard REJECT (never falls through to "maybe link
anyway") in two cases:
  - same issuer, DIFFERENT security type: a DVR or preference share is a
    different security class with its own independent price series and must
    never be merged with the ordinary shares.
  - same issuer/type but OVERLAPPING date ranges: not a clean handover: two
    ISINs trading concurrently under the same issuer+type is not the
    "old ISIN retires, new one takes over" pattern this rule is built for.
Anything the structural rule doesn't decide is left UNLINKED and reported,
never guessed -- a wrong link silently splices two unrelated companies'
price histories together, which is strictly worse than a feature that's a
few years short of history.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import duckdb
import pandas as pd

SOURCE_NAME = "ISIN_LINEAGE_NSDL_STRUCTURAL"


@dataclass(frozen=True)
class IsinStructure:
    prefix: str    # e.g. "INE", "INF", "IN9"
    issuer: str    # 4 chars
    sectype: str   # 2 chars
    serial: int
    raw: str

    @property
    def same_issuer_type(self):
        return (self.prefix, self.issuer, self.sectype)


def parse_isin(isin: str) -> IsinStructure | None:
    if not isinstance(isin, str) or len(isin) != 12:
        return None
    try:
        serial = int(isin[9:11])
    except ValueError:
        return None
    return IsinStructure(prefix=isin[0:3], issuer=isin[3:7], sectype=isin[7:9], serial=serial, raw=isin)


EQUITY_ISIN_PREFIXES = ("INE", "IN9")  # ordinary equity + DVR share classes; excludes INF (fund/ETF units)


def build_isin_date_ranges(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """One row per (symbol, isin): first/last observed trade_date in prices_eod.

    Restricted to INE/IN9 (equity, including DVR share classes) up front.
    INF (fund/ETF unit) ISINs use a different NSDL allocation scheme --
    alphanumeric in the positions this rule treats as a numeric serial (e.g.
    INF209KB1O58 has 'O5' where an equity ISIN would have a 2-digit serial)
    -- so they are not equity and not in scope for this structural rule at
    all, the same exclusion the prior project made at the universe-definition
    stage. Filtering here, rather than after generating candidates, keeps
    "ambiguous" meaning what it should: a genuine equity case the rule could
    not decide, not a fund unit the rule was never meant to parse.
    """
    prefix_filter = " OR ".join(f"isin LIKE '{p}%'" for p in EQUITY_ISIN_PREFIXES)
    df = con.execute(
        f"""
        SELECT symbol, isin, MIN(trade_date) AS first_date, MAX(trade_date) AS last_date
        FROM prices_eod
        WHERE series = 'EQ' AND ({prefix_filter})
        GROUP BY symbol, isin
        """
    ).fetchdf()
    df["first_date"] = pd.to_datetime(df["first_date"]).dt.date
    df["last_date"] = pd.to_datetime(df["last_date"]).dt.date
    return df


def build_lineage(con: duckdb.DuckDBPyConnection) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (lineage_df, ambiguous_df).

    lineage_df: one row per ISIN that belongs to a resolved chain (including
    length-1 chains, i.e. every ISIN gets an entity_id -- its own if never
    linked to anything).
    ambiguous_df: candidate pairs the structural rule could not decide,
    with the specific reason, for reporting -- never silently dropped.
    """
    ranges = build_isin_date_ranges(con)

    lineage_rows = []
    ambiguous_rows = []
    linked_isins = set()

    for symbol, group in ranges.groupby("symbol"):
        group = group.sort_values("first_date").reset_index(drop=True)
        if len(group) < 2:
            continue  # nothing to link; handled by the "every ISIN gets an entity" fallback below

        structs = [parse_isin(isin) for isin in group["isin"]]
        for i in range(len(group) - 1):
            a, b = structs[i], structs[i + 1]
            row_a, row_b = group.iloc[i], group.iloc[i + 1]
            if a is None or b is None:
                ambiguous_rows.append(dict(symbol=symbol, isin_a=row_a["isin"], isin_b=row_b["isin"],
                                            reason="unparseable_isin_structure"))
                continue

            if a.prefix == b.prefix and a.issuer == b.issuer and a.sectype != b.sectype:
                ambiguous_rows.append(dict(symbol=symbol, isin_a=a.raw, isin_b=b.raw,
                                            reason="same_issuer_different_security_type_HARD_REJECT"))
                continue

            if a.prefix != b.prefix or a.issuer != b.issuer or a.sectype != b.sectype:
                ambiguous_rows.append(dict(symbol=symbol, isin_a=a.raw, isin_b=b.raw,
                                            reason="different_issuer_or_type_not_a_reissue_candidate"))
                continue

            if not (b.serial > a.serial):
                ambiguous_rows.append(dict(symbol=symbol, isin_a=a.raw, isin_b=b.raw,
                                            reason="serial_does_not_increase_in_date_order"))
                continue

            if row_a["last_date"] >= row_b["first_date"]:
                ambiguous_rows.append(dict(symbol=symbol, isin_a=a.raw, isin_b=b.raw,
                                            reason="overlapping_date_ranges_not_a_clean_handover"))
                continue

            # All conditions satisfied: deterministic link.
            lineage_rows.append(dict(
                isin=b.raw, predecessor_isin=a.raw, transition_date=row_b["first_date"],
            ))
            linked_isins.add(a.raw)
            linked_isins.add(b.raw)

    # Resolve chains: predecessor pointers -> entity_id = earliest ISIN in the chain.
    pred_map = {r["isin"]: r["predecessor_isin"] for r in lineage_rows}
    transition_map = {r["isin"]: r["transition_date"] for r in lineage_rows}

    def resolve_entity(isin: str) -> str:
        seen = set()
        cur = isin
        while cur in pred_map and cur not in seen:
            seen.add(cur)
            cur = pred_map[cur]
        return cur

    all_isins = set(ranges["isin"])
    now = dt.datetime.now()
    final_rows = []
    for isin in all_isins:
        entity_id = resolve_entity(isin)
        known_date = transition_map.get(isin, ranges.loc[ranges["isin"] == isin, "first_date"].iloc[0])
        final_rows.append(dict(
            isin=isin,
            entity_id=entity_id,
            predecessor_isin=pred_map.get(isin),
            link_method="nsdl_structural" if isin in pred_map else "chain_start",
            known_date=known_date,
            fetched_at=now,
            source=SOURCE_NAME,
            revision_seq=1,
        ))

    lineage_df = pd.DataFrame(final_rows)
    ambiguous_df = pd.DataFrame(ambiguous_rows) if ambiguous_rows else pd.DataFrame(
        columns=["symbol", "isin_a", "isin_b", "reason"]
    )
    return lineage_df, ambiguous_df


def load_lineage_to_duckdb(con: duckdb.DuckDBPyConnection, lineage_df: pd.DataFrame, ambiguous_df: pd.DataFrame) -> tuple[int, int]:
    con.execute("DELETE FROM isin_lineage")  # lineage is a fully-recomputed resolution layer, not append-only facts
    con.register("lin_new", lineage_df)
    con.execute("INSERT INTO isin_lineage SELECT * FROM lin_new")
    con.unregister("lin_new")

    con.execute("DELETE FROM isin_lineage_ambiguous")
    if not ambiguous_df.empty:
        amb = ambiguous_df.copy()
        amb["detected_at"] = dt.datetime.now()
        con.register("amb_new", amb)
        con.execute("INSERT INTO isin_lineage_ambiguous SELECT * FROM amb_new")
        con.unregister("amb_new")
    return len(lineage_df), len(ambiguous_df)


def build_entity_resolver(con: duckdb.DuckDBPyConnection, as_of: dt.date | None = None) -> dict[str, str]:
    """isin -> entity_id map, point-in-time: a link only established later
    (known_date > as_of) must not be used to resolve entities as-of an
    earlier date -- otherwise a feature computed for a historical date would
    use lineage knowledge that didn't exist yet."""
    if as_of is None:
        df = con.execute("SELECT isin, entity_id FROM isin_lineage").fetchdf()
    else:
        df = con.execute(
            "SELECT isin, entity_id, known_date FROM isin_lineage WHERE known_date <= ?", [as_of]
        ).fetchdf()
    return dict(zip(df["isin"], df["entity_id"]))
