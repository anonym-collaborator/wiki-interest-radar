"""Polite HTTP client for Wikimedia APIs: throttling, retries, record/replay."""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import config


class ApiError(RuntimeError):
    def __init__(self, status: int | None, url: str, detail: str):
        super().__init__(f"HTTP {status} for {url}: {detail}")
        self.status = status
        self.url = url
        self.detail = detail


class OfflineMiss(RuntimeError):
    """Raised in offline/replay mode when a response is not available locally."""


def log(msg: str) -> None:
    if not os.environ.get("WIR_QUIET"):
        print(f"[wir] {msg}", file=sys.stderr, flush=True)


def _key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]


class Client:
    """Sequential client. `get_json` returns (status, payload); 404 is a normal
    answer for the pageviews API ("zero or not loaded"), other errors raise."""

    def __init__(self, offline: bool = False, replay_dir: str | None = None,
                 record_dir: str | None = None, min_interval: float = config.MIN_INTERVAL_S):
        self.offline = offline
        self.replay_dir = Path(replay_dir) if replay_dir else (
            Path(os.environ["WIR_REPLAY_DIR"]) if os.environ.get("WIR_REPLAY_DIR") else None)
        self.record_dir = Path(record_dir) if record_dir else (
            Path(os.environ["WIR_RECORD_DIR"]) if os.environ.get("WIR_RECORD_DIR") else None)
        self.min_interval = min_interval
        self._last = 0.0
        self.requests = 0
        self.throttled = 0

    # -- replay / record -------------------------------------------------
    def _replay(self, url: str):
        path = self.replay_dir / f"{_key(url)}.json"
        if not path.exists():
            raise OfflineMiss(f"no recorded response for {url}")
        rec = json.loads(path.read_text(encoding="utf-8"))
        return rec["status"], rec["body"]

    def _record(self, url: str, status: int, body) -> None:
        self.record_dir.mkdir(parents=True, exist_ok=True)
        rec = {"url": url, "status": status, "body": body}
        (self.record_dir / f"{_key(url)}.json").write_text(
            json.dumps(rec, ensure_ascii=False), encoding="utf-8")

    # -- live --------------------------------------------------------------
    def get_json(self, url: str):
        if self.replay_dir is not None:
            return self._replay(url)
        if self.offline:
            raise OfflineMiss(f"offline mode: {url} is not cached")
        last_error = ""
        for attempt in range(config.MAX_RETRIES):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            req = urllib.request.Request(url, headers={
                "User-Agent": config.user_agent(),
                "Accept": "application/json",
            })
            self._last = time.monotonic()
            self.requests += 1
            try:
                with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT_S) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    status = resp.status
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", "replace")
                if e.code == 404:
                    try:
                        body = json.loads(raw)
                    except ValueError:
                        body = {"detail": raw[:300]}
                    status = 404
                elif e.code in (429, 500, 502, 503, 504):
                    self.throttled += 1
                    ra = e.headers.get("Retry-After", "")
                    delay = float(ra) if ra.strip().isdigit() else min(60.0, 5.0 * 2 ** attempt)
                    log(f"HTTP {e.code} from {url.split('?')[0][:70]}..., waiting {delay:.0f}s "
                        f"(attempt {attempt + 1}/{config.MAX_RETRIES})")
                    time.sleep(delay + random.uniform(0, 1))
                    last_error = f"HTTP {e.code}"
                    continue
                else:
                    raise ApiError(e.code, url, raw[:300]) from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                delay = min(30.0, 2.0 * 2 ** attempt)
                log(f"network error ({e}); retrying in {delay:.0f}s")
                time.sleep(delay)
                last_error = str(e)
                continue
            if self.record_dir is not None:
                self._record(url, status, body)
            return status, body
        raise ApiError(None, url, f"gave up after {config.MAX_RETRIES} attempts ({last_error})")
