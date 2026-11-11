"""Run local B acceptance checks without Oracle, credentials or external calls."""

from pathlib import Path
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    checks = (
        ("B unit/API regressions", ["-m", "pytest", "tests/api", "-q"]),
        ("Frozen B2 examples", ["contracts/b2/validate.py"]),
        ("Two synthetic API journeys", ["-m", "tests.api.smoke"]),
    )
    for label, args in checks:
        print(f"Checking: {label}", flush=True)
        completed = subprocess.run([sys.executable, *args], cwd=root, check=False)
        if completed.returncode:
            print(f"FAIL: {label}", flush=True)
            return completed.returncode
    print("PASS: local B checks only; live integration gates remain unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
