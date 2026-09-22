# Phase 1 — Data Source Licensing Assessment

Assessed 2026-09-19. This governs what got built and what didn't.

## A. NSE bhavcopy (prices) — PROCEED, with conditions

Source: `nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip`

- NSE's Data Usage and Data Sharing Policy distinguishes personal/informational/
  educational use (permitted, no fee) from commercial exploitation (requires a
  paid license from NSE Data, board-approved pricing). NSE's newer MCP terms
  additionally bar using the data to train/fine-tune AI models or in
  third-party commercial applications.
- This project is personal quantitative research: data is fetched, cached
  locally, and used to compute signals for the account holder's own decisions.
  That fits the permitted envelope as written.
- Conditions that keep it there: don't redistribute the raw bhavcopy files or
  the cached warehouse to third parties, don't sell signals or outputs
  derived from it, don't publish the raw data. If this project's outputs are
  ever shared, published, or monetized, re-check the commercial licensing
  requirement before doing so — that changes the analysis.
- Rate limits: no published hard number for archive downloads; used the
  conservative 3 req/sec, 0.5-1s sleep convention already standard among
  open-source NSE clients (jugaad-data, nsepy, nselib). Confirmed working
  live against real files (see samples below).

## B. BSE XBRL filings via bseindia.com — DO NOT BUILD, alternative found

Source as originally specified: `bseindia.com/corporates/ann.html`

- BSE's website policy and disclaimer state: "Any reproduction, redistribution
  or transmission, for consideration or otherwise, of any information
  contained on the Website is strictly prohibited." This is a blanket clause
  with no carve-out for regulatory filings, XBRL, or corporate announcements.
- Read literally, this prohibits exactly what a fetcher-and-cache pipeline
  does (reproducing and storing the content), regardless of commercial
  intent. This is broader and more restrictive than NSE's terms.
- Per your instruction ("if a source prohibits it, say so and stop"): stopping
  on bseindia.com direct scraping.
- **Alternative that resolves this**: NSE hosts financial-results filings for
  its own listed universe under its *own* domain and terms —
  `nseindia.com/api/corporates-financial-results` for metadata (including the
  exchange dissemination timestamp) and
  `nsearchives.nseindia.com/corporate/xbrl/*.xml` for the underlying XBRL.
  The XML is tagged under the `in-bse-fin` namespace even when served by
  NSE — it's SEBI's common national taxonomy for financial results, not a
  BSE-exclusive format — so this is the same regulatory content, sourced
  under NSE's already-assessed terms instead of BSE's. Since this project's
  universe is NSE equities, coverage is complete; BSE-only listings (not
  cross-listed on NSE) are out of scope and not needed here.
- This is implemented and proven against real data (Section D below), so
  Phase 1's fundamentals requirement is met without touching bseindia.com.

## C. Screener.in — DO NOT BUILD (per your own instruction, confirmed)

- Screener's Terms of Service prohibit modifying or copying "the materials,"
  using them "for any commercial purpose, or for any public display," and
  prohibit mirroring or transferring materials to another server. There is no
  scraping-specific clause, but the copy/mirror/no-commercial-use language
  covers what a fetcher would do.
- robots.txt disallows `/company/source/quarter/*` (a quarterly-data path)
  among a few other paths — a mechanical signal pointing the same direction
  as the ToS text.
- Conclusion: not building this. Fundamentals come from NSE-hosted XBRL only,
  as you directed as the fallback.

## D. NSE Integrated Filing-Financial XBRL (post-April-2025 format) — PROCEED, same terms as A/B

Source: `nseindia.com/api/integrated-filing-results` (metadata) and
`nsearchives.nseindia.com/corporate/xbrl/*.xml` (documents) — same two hosts
already assessed and cleared in A and B above. The new SEBI taxonomy
(`in-capmkt`, replacing `in-bse-fin`) is a different regulator-issued XBRL
schema, not a different data source or a different site's terms — the same
reasoning in B (NSE-hosted regulatory XBRL under NSE's own terms, regardless
of which SEBI taxonomy version tags it) applies unchanged. No new licensing
question; see `FUNDAMENTALS.md`'s Integrated Filing coverage report for the
technical findings.

## Known downstream constraint (flagging now, not a licensing issue)

The quarterly XBRL filings carry P&L line items and EPS every quarter, but
full balance-sheet tags (total assets, equity, debt) only appear in
annual/half-yearly filings under SEBI's disclosure requirements. Value/Quality
factors that need book value or leverage (P/B, ROCE, D/E, Piotroski, Altman Z)
will therefore refresh at a lower cadence than earnings-based factors
(earnings yield, EPS growth). This is a real data constraint to design around
in Phase 2/3, not a bug — flagging it now so it isn't a surprise later.
