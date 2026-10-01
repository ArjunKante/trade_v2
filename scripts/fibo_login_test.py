"""One-off Angel One SmartAPI login smoke test -- run once after .env is
filled in. Prints ONLY 'login OK' or 'LOGIN FAILED: <redacted code>', per
instruction. Never prints, logs, or persists the session/tokens anywhere.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.auth import login


def main():
    result = login()
    if result.ok:
        print("login OK")
    else:
        print(f"LOGIN FAILED: {result.status}")


if __name__ == "__main__":
    main()
