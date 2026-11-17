"""Keeps data/fibo_live/v1/events.jsonl -- the Fibo live paper-trading
system's entire evidence trail -- backed up to the git remote after every
evening-job run, not left as the only copy on one laptop.

WHY this one file inside `data/`, which this project otherwise never
tracks (.gitignore, OPERATIONS.md): it is not NSE market data (the
licensing reason the rest of `data/` is ignored) -- it is this laptop's
own paper-trading decisions, logged before any outcome was known. There is
exactly one copy, on one laptop that has already crashed twice in a single
week; losing it does not just lose data, it invalidates the forward test
(a signal re-logged after the fact proves nothing about whether it was
known before its outcome). A git commit's own timestamp is independent
evidence that it was logged before the outcome existed -- see
OPERATIONS.md for the full reasoning and the .gitignore exception this
depends on.

NEVER BLOCKS THE JOB: every git subprocess failure (no network, no
upstream configured, nothing changed, a hook rejecting the commit, git
itself missing) is caught, logged, and swallowed -- the same
run_unattended discipline scheduler_support.py already applies to
everything else in these scripts. A failed push here must never be
mistaken for a failed paper-trading run; it just means the laptop is
carrying one more unpushed commit until the next one succeeds.
"""
from __future__ import annotations

import datetime as dt
import subprocess
import sys
import time
from pathlib import Path

from fibo_live.config import ROOT

# Mirrors data_layer.db's own warehouse-lock retry constants exactly
# (scripts/fibo_evening.py's DB_OPEN_MAX_ATTEMPTS/DB_OPEN_RETRY_BASE_
# SECONDS) -- same shape of problem (transient file-lock contention from
# another process touching the same repo/file at the same moment), same
# fix. 5 attempts, base 3s, doubling: sleeps of 3/6/12/24s.
GIT_PULL_MAX_ATTEMPTS = 5
GIT_PULL_RETRY_BASE_SECONDS = 3


def _run_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=60,
    )


def _looks_like_index_lock_contention(output: str) -> bool:
    """git's own wording for 'another git process is already running
    here' -- e.g. "fatal: Unable to create '.../.git/index.lock': File
    exists." -- confirmed transient: it clears the instant the other
    process's git operation finishes, same as a DuckDB file-lock
    IOException clears the instant the holder closes the connection."""
    lowered = output.lower()
    return "index.lock" in lowered or "unable to create" in lowered


class GitPullError(Exception):
    """Raised by pull_before_appending when the pre-run pull fails for a
    reason OTHER than transient index.lock contention (that case retries
    with backoff and, on exhaustion, calls sys.exit(1) instead -- see
    pull_before_appending's own docstring for why). Callers must let this
    propagate (main() aborts, run_unattended logs the full traceback and
    still exits 0), never catch and continue against a possibly-stale
    events.jsonl."""


def pull_before_appending(log) -> None:
    """Merge pull -- must be the FIRST thing fibo_evening.py's main() does,
    before any append_event call touches events.jsonl on disk.

    CHANGED 2026-11-15 (BUGS.md, OPERATIONS.md's "Evening job dead-man's
    switch" sections): this was `git pull --ff-only` until a
    single-writer assumption in what is actually a two-writer system
    (GitHub Actions commits from the morning job, this laptop commits
    from the evening job, both to the same events.jsonl) blocked every
    evening run for 7 straight trading days, 2026-11-06 through
    2026-11-13, the moment the two histories diverged -- which is the
    NORMAL state for two independent writers to the same file, not an
    error. `--ff-only` treated normal, expected divergence as a fatal
    refusal, with no automatic recovery and no visible alert (the exact
    gap the dead-man's switch above now also covers).

    FIXED by switching to an ordinary merge pull (`--no-rebase`,
    explicit regardless of this machine's `pull.rebase` config) plus
    `.gitattributes`'s `merge=union` driver on `data/fibo_live/v1/*.jsonl`:
    the file is append-only and every line carries its own timestamp, so
    line order is not semantically load-bearing, which is exactly the
    precondition a union merge (keep both sides' lines, never a manual
    conflict) needs to be safe. `fibo_live/eventlog.py`'s `read_events()`
    also dedupes by `event_id` as cheap insurance against a line
    appearing on both sides of a merge. See
    `tests/test_fibo_git_union_merge.py` for a real two-branch merge
    proving no loss and no duplication.

    NEVER REBASE HERE: rebase rewrites committer timestamps, and a
    commit's own timestamp is this project's provenance evidence that an
    event was logged before its outcome was known (this module's own
    docstring). A merge commit's timestamp is new, but it never alters
    the timestamp already recorded on the commits being merged.

    UNLIKE this module's push (sync_events_log_to_git, best-effort,
    every failure swallowed): this still RAISES on failure. A union
    merge resolves any divergence IN events.jsonl automatically and
    never produces a conflict there; a GitPullError here now means
    something else is genuinely wrong (no network, a conflict in some
    OTHER tracked file, a corrupted checkout) -- still worth refusing to
    run against, since proceeding on an unknown repo state is exactly
    the scenario this function exists to prevent.

    RETRY WITH BACKOFF on index.lock contention specifically (BUGS.md
    Bug #31, 2026-11-18): this job now runs at 20:00 IST, inside the
    window active development work happens in this same local
    repository, and a `git commit`/`git add` from that work can hold
    `.git/index.lock` for the brief moment this job's own `git pull`
    tries to run -- transient by nature, confirmed in principle the same
    way `_open_warehouse_with_retry` confirmed DuckDB's file lock is
    transient (it clears the instant the other process's git operation
    finishes). Up to `GIT_PULL_MAX_ATTEMPTS` attempts, `GIT_PULL_RETRY_
    BASE_SECONDS` doubling backoff -- same constants, same shape as the
    DuckDB fix. A pull failure NOT recognized as lock contention is not
    retried at all (a real conflict or no network will not resolve
    itself by waiting) and raises GitPullError immediately, as before.

    On exhausting all attempts against persistent lock contention: calls
    sys.exit(1), deliberately a SystemExit rather than a raised
    GitPullError, so it is NOT caught by run_unattended's `except
    Exception` and actually terminates the process non-zero -- the same
    reasoning as `_open_warehouse_with_retry`'s own sys.exit(1): Task
    Scheduler's own run history becomes a second, independent signal on
    top of the dead-man's switch already going overdue (the heartbeat is
    never reached either way, from this path or the ordinary
    GitPullError path)."""
    output = ""
    for attempt in range(1, GIT_PULL_MAX_ATTEMPTS + 1):
        result = _run_git("pull", "--no-rebase")
        output = (result.stdout.strip() + " " + result.stderr.strip()).strip()
        if result.returncode == 0:
            log(f"  git pull --no-rebase: {output or 'already up to date'}")
            return
        if not _looks_like_index_lock_contention(output) or attempt == GIT_PULL_MAX_ATTEMPTS:
            break
        delay = GIT_PULL_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
        log(f"  git pull --no-rebase: index.lock contention (attempt {attempt}/{GIT_PULL_MAX_ATTEMPTS}): "
            f"{output} -- retrying in {delay}s...")
        time.sleep(delay)

    if _looks_like_index_lock_contention(output):
        log(f"FATAL: git pull --no-rebase still locked after {GIT_PULL_MAX_ATTEMPTS} attempts: "
            f"{output}. LIKELY HOLDER: a concurrent git operation (a commit, another pull) in "
            f"this same working copy -- this job runs at 20:00 IST, inside the window active "
            f"development work happens here. Action: let the next scheduled run retry, or run "
            f"this script by hand once the other git operation has finished. Exiting non-zero "
            f"so this is visible in Task Scheduler's own run history, in addition to the "
            f"dead-man's switch going overdue.")
        sys.exit(1)

    raise GitPullError(
        f"git pull --no-rebase failed ({result.returncode}): {output} -- refusing to run "
        f"against a possibly-stale or conflicted events.jsonl. Resolve manually before "
        f"re-running (a clean merge of events.jsonl should never conflict -- see "
        f".gitattributes's merge=union driver -- so a failure here points at something "
        f"else: no network, a conflict in a different tracked file, or a corrupted checkout)."
    )


def sync_events_log_to_git(path: Path, log, job_label: str = "Fibo evening events") -> None:
    """Stages `path`, commits iff there is something new to commit, and
    pushes -- each step best-effort and logged, never raised. The common
    case (an idempotent-skip or stale-data-refusal run that appended
    nothing new) is a clean no-op, logged as such, not treated as a
    failure.

    `job_label` names which job produced the commit (e.g. "Fibo morning
    events" vs "Fibo evening events") -- both jobs call this same
    function, and a commit message that always said "evening" made every
    morning-job commit look like it came from the wrong job."""
    try:
        rel = str(path.relative_to(ROOT))
    except ValueError:
        rel = str(path)

    try:
        add = _run_git("add", "--", rel)
        if add.returncode != 0:
            log(f"  git sync: 'git add {rel}' failed ({add.returncode}): {add.stderr.strip()}")
            return

        unchanged = _run_git("diff", "--cached", "--quiet", "--", rel)
        if unchanged.returncode == 0:
            log(f"  git sync: no changes to {rel} this run -- nothing to commit.")
            return

        message = f"{job_label} -- synced {dt.date.today().isoformat()}"
        commit = _run_git("commit", "-m", message, "--", rel)
        if commit.returncode != 0:
            log(f"  git sync: commit failed ({commit.returncode}): {commit.stderr.strip()}")
            return
        log(f"  git sync: committed {rel} ({message!r}).")

        push = _run_git("push")
        if push.returncode != 0:
            log(f"  git sync: push failed ({push.returncode}) -- will retry next run: {push.stderr.strip()}")
            return
        log("  git sync: pushed.")
    except Exception as e:
        log(f"  git sync: unexpected error, skipping ({type(e).__name__}: {e})")
