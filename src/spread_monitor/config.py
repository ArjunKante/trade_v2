"""Loads the symbol list from a plain-text config file, so the measured
set can change without touching any code."""
from __future__ import annotations

from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "spread_monitor_symbols.txt"


def load_symbols(path: Path = DEFAULT_CONFIG_PATH) -> list[str]:
    """One symbol per line; blank lines and lines starting with '#' are
    ignored. Raises FileNotFoundError if the config file is missing --
    never silently falls back to an empty or hardcoded list."""
    lines = path.read_text(encoding="utf-8").splitlines()
    symbols = [line.strip().upper() for line in lines if line.strip() and not line.strip().startswith("#")]
    if not symbols:
        raise ValueError(f"{path} contains no symbols")
    return symbols
