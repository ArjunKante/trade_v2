"""Study-agnostic overlay data structures for src/viz/'s plotting tools.

`src/viz/` knows nothing about POC, Fibo, or box theory -- each strategy
supplies its own `Overlay` via its own adapter module (e.g. `src/viz/
poc_adapter.py`). Plain dataclasses, no strategy-specific field names
anywhere in this file.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Level:
    """A horizontal price level, drawn across the full chart width."""
    price: float
    label: str
    color: str = "tab:blue"
    linestyle: str = "--"


@dataclass
class Band:
    """A shaded price zone between two levels (e.g. a golden zone, or a
    box top/bottom range)."""
    low: float
    high: float
    label: str
    color: str = "tab:blue"
    alpha: float = 0.12


@dataclass
class VMarker:
    """A vertical marker at a specific timestamp (touch candle, confirm
    candle, entry fill, exit)."""
    ts: pd.Timestamp
    label: str
    color: str = "dimgray"
    linestyle: str = ":"


@dataclass
class PriceMarker:
    """A marker on the price axis at (ts, price) -- an entry or exit
    fill, drawn as a triangle pointing in the trade's own direction.

    `direction` defaults to "long" so every existing adapter (all
    long-only so far) renders exactly as before. For a SHORT trade
    (`direction="short"`), the renderer flips which `kind` points up vs
    down: a short's "entry" is a SELL (opening the position) so it
    renders like a long's "exit" (down, dark); a short's "exit" is a BUY
    (covering) so it renders like a long's "entry" (up, bright) -- this
    is deliberate, so a short trade reads as structurally different from
    a long one at a glance, not just as a long trade sitting upside down
    at different price levels."""
    ts: pd.Timestamp
    price: float
    kind: str  # "entry" | "exit"
    label: str = ""
    direction: str = "long"  # "long" | "short"


@dataclass
class Overlay:
    """Everything one strategy's adapter supplies for one chart. All
    four annotation kinds are optional and independent -- a skipped
    setup might only ever populate `levels` and `vmarkers`, never
    `price_markers`."""
    levels: list[Level] = field(default_factory=list)
    bands: list[Band] = field(default_factory=list)
    vmarkers: list[VMarker] = field(default_factory=list)
    price_markers: list[PriceMarker] = field(default_factory=list)
    text_panel: list[str] = field(default_factory=list)
    title_suffix: str = ""
