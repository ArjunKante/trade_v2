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
from pathlib import Path

from fibo_live.config import ROOT


def _run_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=60,
    )


class GitPullError(Exception):
    """Raised by pull_before_appending when the pre-run pull fails --
    callers must let this propagate (main() aborts, run_unattended logs
    the full traceback and still exits 0), never catch and continue
    against a possibly-stale events.jsonl."""


def pull_before_appending(log) -> None:
    """Fast-forward-only pull -- must be the FIRST thing fibo_evening.py's
    main() does, before any append_event call touches events.jsonl on
    disk. Once the Fibo morning job runs on GitHub Actions (committing
    and pushing its own setup/trigger/outcome events during market
    hours) while the evening job still runs on this laptop hours later,
    the laptop's checkout can be behind origin by however many morning
    commits happened that day. Pulling FIRST -- before this run appends
    a single line -- means the local file already contains the
    morning's lines before the evening job's own new lines are appended
    after them, so every subsequent commit is a clean linear fast-
    forward: there is never a divergent history to merge, and never a
    rejected non-fast-forward push.

    UNLIKE this module's push (sync_events_log_to_git, best-effort,
    every failure swallowed): this RAISES on failure. Proceeding on a
    stale local events.jsonl is exactly the scenario this exists to
    prevent -- silently computing against a watchlist that doesn't yet
    include this morning's events, or a non-fast-forward push rejected
    hours later with this run's own commit stuck on top of it. One
    precondition this depends on for a plain `--ff-only` to ever
    succeed: fibo_morning.py must be the ONLY thing that ever commits to
    this repo from anywhere else -- the laptop never runs it once the
    GitHub Actions schedule is live (see OPERATIONS.md)."""
    result = _run_git("pull", "--ff-only")
    output = (result.stdout.strip() + " " + result.stderr.strip()).strip()
    if result.returncode != 0:
        raise GitPullError(
            f"git pull --ff-only failed ({result.returncode}): {output} -- refusing to run "
            f"against a possibly-stale events.jsonl. Resolve manually (check for a diverged "
            f"history -- this should only ever be a clean fast-forward) before re-running."
        )
    log(f"  git pull --ff-only: {output or 'already up to date'}")


def sync_events_log_to_git(path: Path, log) -> None:
    """Stages `path`, commits iff there is something new to commit, and
    pushes -- each step best-effort and logged, never raised. The common
    case (an idempotent-skip or stale-data-refusal run that appended
    nothing new) is a clean no-op, logged as such, not treated as a
    failure."""
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

        message = f"Fibo evening events -- synced {dt.date.today().isoformat()}"
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
