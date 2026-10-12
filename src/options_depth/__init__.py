"""Forward collector for live NIFTY index-option bid/ask depth.

RESEARCH/COLLECTION ONLY -- no strategy, no analysis, no signal, no
decision of any kind is made anywhere in this package. It exists to
answer, going forward, the one question OPTIONS_FEASIBILITY.md's
retroactive audit could not: what does this market's own quoted depth
actually look like, day after day, once it is actually recorded (that
audit's verdict -- BLOCKED for multi-year HISTORICAL backtesting -- is
untouched by this package; see that document's Status section for the
live-depth check this package follows up on).

Separate from Fibo, momentum, swing, and per_stock -- nothing in those
packages is imported or modified here. `src/fibo/auth.login` (the one
hardened, credential-safe login path) and `src/spread_monitor/
market_hours.check_market_hours` (a generic weekday/session-window guard,
not equity-specific) are reused read-only, the same way every other
script in this project already reuses them.

THIS DATA CANNOT BE RE-ACQUIRED. A missed or lost snapshot of a given
option contract's depth at a given moment is gone forever -- unlike
every price table in `data_layer/`, there is no archive, vendor, or
later re-download that can backfill a quote this collector failed to
take (OPTIONS_FEASIBILITY.md's own verdict is exactly this fact applied
retroactively: once a contract expires, Angel's own master drops it and
even ITS OWN historical endpoint can no longer serve it). `data/
options_depth/` is gitignored, same as the rest of `data/` (NSE market
data, not source code) -- so git is NOT this log's backup. It exists on
this one laptop only, until copied out. The user has stated they will
copy it to Google Drive periodically; this package does not automate
that copy itself (no credential, API, or cloud-storage integration
exists anywhere in this project, and building one was not asked for) --
it is a standing manual step, not a wired-up job like `fibo_live.
git_sync`'s commit+push. Treat an old, un-backed-up copy of this file as
the only copy of whatever it contains.
"""
