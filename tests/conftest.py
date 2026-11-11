"""Shared test setup. A's tests import their sibling helper as a top-level module
(`from handoff_adapter import ...`), so the tests directory stays on sys.path."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
