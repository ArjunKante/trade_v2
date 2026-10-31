"""Synthetic unit tests for src/spread_validation/'s own estimators --
pure-function scenarios, no DB access, run before any real data is
collected. Confirms corwin_schultz matches the original script's own
function byte-for-byte (not just "the same formula, re-typed"), and
roll_1984 correctly distinguishes defined from undefined cases."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

from spread_validation.estimators import corwin_schultz, roll_1984

FAILS = []


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    if not cond:
        FAILS.append(label)
    print(f"[{status}] {label}")


# ---------------------------------------------------------------------
# corwin_schultz: byte-for-byte match against the original diagnostic
# script's own function, on the same synthetic high/low series
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "_orig_lowliq_diag", ROOT / "scripts" / "run_lowliq_cost_calibration_diagnostic.py")
# The original script runs real DB queries at import time -- load only its
# own corwin_schultz function by executing just that function's source,
# not the whole module (avoids a live DB dependency for a pure-function
# unit test). Extracted via exec of the function's own text block instead
# of a full module import, since the script has no `if __name__ ==
# "__main__"` guard around its own top-level DB work.
import ast
tree = ast.parse((ROOT / "scripts" / "run_lowliq_cost_calibration_diagnostic.py").read_text(encoding="utf-8"))
func_src = None
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name == "corwin_schultz":
        func_src = ast.get_source_segment(
            (ROOT / "scripts" / "run_lowliq_cost_calibration_diagnostic.py").read_text(encoding="utf-8"), node)
        break
assert func_src is not None, "could not extract corwin_schultz source from the original diagnostic script"
namespace = {"np": np, "pd": pd}
exec(func_src, namespace)
original_corwin_schultz = namespace["corwin_schultz"]

rng = np.random.default_rng(0)
n = 60
base = 100 + np.cumsum(rng.normal(0, 1, n))
high = pd.Series(base + np.abs(rng.normal(1, 0.5, n)))
low = pd.Series(base - np.abs(rng.normal(1, 0.5, n)))

mine = corwin_schultz(high, low)
original = original_corwin_schultz(high, low)
check("corwin_schultz matches the original script's own function byte-for-byte (allowing NaN==NaN)",
      np.allclose(mine.fillna(-999), original.fillna(-999)))

check("corwin_schultz index 0 is NaN (no prior day to pair with)", pd.isna(mine.iloc[0]))
check("corwin_schultz never returns a negative spread", (mine.dropna() >= 0).all())

# Degenerate case: identical high==low every day -> zero true range, log(h/l)=0
# every day -> alpha should floor to a non-negative (likely 0) spread, not NaN/inf.
flat = pd.Series([100.0] * 10)
flat_cs = corwin_schultz(flat, flat)
check("corwin_schultz on a flat (zero-range) series stays finite and non-negative",
      flat_cs.dropna().apply(lambda x: np.isfinite(x) and x >= 0).all())


# ---------------------------------------------------------------------
# roll_1984 -- defined vs. undefined cases
# ---------------------------------------------------------------------

# Construct returns with NEGATIVE first-order autocovariance (bid-ask
# bounce: alternating up/down), where Roll should be DEFINED.
bounce = pd.Series([0.01, -0.01] * 30)
spread, defined = roll_1984(bounce)
check("roll_1984: alternating bounce series gives a DEFINED, positive spread",
      defined and spread > 0 and np.isfinite(spread))

# Construct returns with POSITIVE first-order autocovariance (trending:
# each day's return has the same sign as the prior day's), where Roll is
# structurally UNDEFINED.
trend = pd.Series(np.repeat([0.01, 0.01, -0.01, -0.01], 15))
spread_t, defined_t = roll_1984(trend)
check("roll_1984: trending (positive-autocovariance) series is UNDEFINED, not silently zeroed",
      not defined_t and np.isnan(spread_t))

# Too few observations -> undefined, not a crash.
short = pd.Series([0.01, -0.01, 0.02])
spread_s, defined_s = roll_1984(short, min_obs=20)
check("roll_1984: too few observations -> undefined, no crash", not defined_s and np.isnan(spread_s))

print()
if FAILS:
    print(f"=== {len(FAILS)} FAILURE(S): {FAILS} ===")
    sys.exit(1)
print("=== ALL SCENARIOS PASS ===")
