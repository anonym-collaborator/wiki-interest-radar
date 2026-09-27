"""SQLite cache: pageview points + which ranges were fetched + raw JSON responses.

Knowing which ranges were fetched is what makes zero-filling correct: the API
omits zero days, so a missing point inside a fetched range is a real zero.
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path

from . import config
from .series import merge_intervals

SCHEMA = """
CREATE TABLE IF NOT EXISTS points (
  skey TEXT NOT NULL, ts TEXT NOT NULL, views INTEGER NOT NULL,
  PRIMARY KEY (skey, ts));
CREATE TABLE IF NOT EXISTS coverage (
  skey TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS coverage_skey ON coverage(skey);
CREATE TABLE IF NOT EXISTS http_json (
  url TEXT PRIMARY KEY, status INTEGER NOT NULL, body TEXT NOT NULL, fetched_at REAL NOT NULL);
"""


def series_key(kind: str, project: str, title: str, access: str, agent: str, gran: str) -> str:
    return "|".join((kind, project, title, access, agent, gran))


class Cache:
    def __init__(self, path: Path | None = None):
        path = Path(path) if path else config.cache_dir() / "cache.sqlite"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        # Several agent sessions may share one cache: wait for locks instead of failing.
        self.db = sqlite3.connect(str(path), timeout=60)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self.hits = 0
        self.misses = 0

    def close(self) -> None:
        self.db.commit()
        self.db.close()

    # -- series ----------------------------------------------------------
    def coverage(self, skey: str) -> list[tuple[date, date]]:
        rows = self.db.execute("SELECT start, end FROM coverage WHERE skey=?", (skey,)).fetchall()
        return [(date.fromisoformat(s), date.fromisoformat(e)) for s, e in rows]

    def add_coverage(self, skey: str, start: date, end: date, monthly: bool) -> None:
        # Never mark the most recent days as final: they may still be loading.
        horizon = date.today() - timedelta(days=config.DATA_LAG_DAYS + 1)
        if not monthly and end > horizon:
            end = horizon
        if end < start:
            return
        merged = merge_intervals(self.coverage(skey) + [(start, end)], 31 if monthly else 1)
        self.db.execute("DELETE FROM coverage WHERE skey=?", (skey,))
        self.db.executemany("INSERT INTO coverage VALUES (?,?,?)",
                            [(skey, s.isoformat(), e.isoformat()) for s, e in merged])
        self.db.commit()

    def put_points(self, skey: str, points: dict[str, int]) -> None:
        self.db.executemany("INSERT OR REPLACE INTO points VALUES (?,?,?)",
                            [(skey, ts, int(v)) for ts, v in points.items()])
        self.db.commit()

    def get_points(self, skey: str, start_ts: str, end_ts: str) -> dict[str, int]:
        rows = self.db.execute(
            "SELECT ts, views FROM points WHERE skey=? AND ts>=? AND ts<=?",
            (skey, start_ts, end_ts)).fetchall()
        return dict(rows)

    # -- raw json (Wikidata / Action API) --------------------------------
    def get_json(self, url: str, max_age_s: float):
        row = self.db.execute("SELECT status, body, fetched_at FROM http_json WHERE url=?",
                              (url,)).fetchone()
        if row and time.time() - row[2] <= max_age_s:
            self.hits += 1
            return row[0], json.loads(row[1])
        return None

    def put_json(self, url: str, status: int, body) -> None:
        self.db.execute("INSERT OR REPLACE INTO http_json VALUES (?,?,?,?)",
                        (url, status, json.dumps(body, ensure_ascii=False), time.time()))
        self.db.commit()
