"""Constants and environment-dependent settings."""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

VERSION = "0.1.0"
SKILL_NAME = "wiki-interest-radar"
# Public home of the skill; used in the User-Agent as the "relevant external website".
PROJECT_URL = "https://github.com/anonym-collaborator/wiki-interest-radar"

PAGEVIEWS_API = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
DATA_START = date(2015, 7, 1)  # first day served by the pageviews API

# Wikimedia API rate limits (2026): 200 req/min for clients with a compliant
# User-Agent, 10 req/min otherwise, at most 3 concurrent requests.
# We stay sequential and below ~170 req/min.
MIN_INTERVAL_S = float(os.environ.get("WIR_MIN_INTERVAL", "0.35"))
MAX_RETRIES = 6
HTTP_TIMEOUT_S = 30

# Days after a month ends before we treat it as complete (loading lag is
# usually hours, sometimes 24h+).
DATA_LAG_DAYS = 2

SKILL_ROOT = Path(__file__).resolve().parents[2]
ASSETS = SKILL_ROOT / "assets"


def user_agent() -> str:
    contact = os.environ.get("WIR_CONTACT", "").strip()
    who = PROJECT_URL if not contact or contact == PROJECT_URL else f"{PROJECT_URL}; {contact}"
    py = f"{sys.version_info.major}.{sys.version_info.minor}"
    return f"{SKILL_NAME}/{VERSION} (+{who}) python-urllib/{py}"


def cache_dir() -> Path:
    env = os.environ.get("WIR_CACHE_DIR")
    if env:
        return Path(env)
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / SKILL_NAME
