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
    the scenario this function exists to prevent."""
    result = _run_git("pull", "--no-rebase")
    output = (result.stdout.strip() + " " + result.stderr.strip()).strip()
    if result.returncode != 0:
        raise GitPullError(
            f"git pull --no-rebase failed ({result.returncode}): {output} -- refusing to run "
            f"against a possibly-stale or conflicted events.jsonl. Resolve manually before "
            f"re-running (a clean merge of events.jsonl should never conflict -- see "
            f".gitattributes's merge=union driver -- so a failure here points at something "
            f"else: no network, a conflict in a different tracked file, or a corrupted checkout)."
        )
    log(f"  git pull --no-rebase: {output or 'already up to date'}")


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
