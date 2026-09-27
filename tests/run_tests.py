#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy>=1.26,<3",
#   "matplotlib>=3.8,<4",
#   "pytest>=8,<9",
#   "pypdf>=4,<7",
# ]
# ///
"""Offline test suite (no network): uv run tests/run_tests.py"""
import sys
from pathlib import Path

import pytest

if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    sys.exit(pytest.main([str(here), "-q", "-p", "no:cacheprovider", *sys.argv[1:]]))
