#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy>=1.26,<3",
#   "matplotlib>=3.8,<4",
# ]
# ///
"""wiki-interest-radar: Wikipedia pageview interest analysis for agents.

Run with uv (installs pinned dependencies on first use):
    uv run scripts/radar.py --help
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wir.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
