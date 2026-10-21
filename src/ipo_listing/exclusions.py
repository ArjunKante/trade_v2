"""Explicit, named exclusions found during Phase 1 bhavcopy validation --
applied as code, not a one-off manual database edit, so re-running
`scripts/ipo_listing_fetch.py` from a fresh database reproduces the same
final usable sample.

KNOWN_DATA_DEFECTS: 3 listings (out of 501 that otherwise fetched 'OK')
whose bars differ from bhavcopy by >5% on LOW specifically, all three
sharing the identical signature -- low_pct_diff=100%, open diverging
34-44%, close matching within 1% -- consistent with a single spurious
near-zero LOW tick in the fetched feed on that one day, not a scale or
identification problem (`IPO_FINDINGS.md` Section 3). Excluded per user
instruction: the first 1-minute candle is exactly what
`PREREGISTRATION_IPO.md` Section 5's ENTRY rule reads, so a corrupted
tick on day 1 is not an acceptable risk to carry into Phase 2 -- named
and recorded here rather than silently dropped.
"""
from __future__ import annotations

KNOWN_DATA_DEFECTS: dict[int, str] = {
    204: ("Archean Chemical Industries Limited (listed 2022-11-21): low_pct_diff=100% vs bhavcopy, "
          "open_diff=44.2%, close matches within 0.0% -- single-tick low-price defect"),
    205: ("Five-Star Business Finance Ltd. (listed 2022-11-21): low_pct_diff=100% vs bhavcopy, "
          "open_diff=36.0%, close matches within 0.2% -- single-tick low-price defect"),
    230: ("Yatharth Hospital & Trauma CARE Services Limited (listed 2023-08-07): low_pct_diff=100% vs bhavcopy, "
          "open_diff=34.7%, close matches within 0.9% -- single-tick low-price defect"),
}
