"""Polite HTTP and raw snapshot storage.

Every response is written untouched to data/raw/<source>/<YYYY-MM-DD>/ with a
JSON sidecar (url, params, fetched_at, sha256) before anything parses it.
Parsers read snapshots back from disk, so they can be fixed and rerun.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from engine.observation import RawSnapshot

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UA = "ChuiTwin/0.1 (Longaeva AI Hackathon research project; polite, rate-limited)"


def data_root() -> Path:
    return Path(os.environ.get("CHUI_DATA_DIR", REPO_ROOT / "data"))


class BlockedError(RuntimeError):
    """The server refused us. We stop; we never try to get around a block."""


class PoliteClient:
    def __init__(self, user_agent: str = DEFAULT_UA, min_interval_s: float = 2.0, max_retries: int = 4,
                 backoff_s: float = 2.0, timeout_s: float = 30.0):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        self.timeout_s = timeout_s
        self._last = 0.0

    def _wait(self) -> None:
        delay = self.min_interval_s - (time.monotonic() - self._last)
        if delay > 0:
            time.sleep(delay)
        self._last = time.monotonic()

    def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> requests.Response:
        for attempt in range(self.max_retries + 1):
            self._wait()
            try:
                r = self.session.get(url, params=params, headers=headers, timeout=self.timeout_s)
            except (requests.ConnectionError, requests.Timeout):
                if attempt == self.max_retries:
                    raise
                time.sleep(self.backoff_s * 2**attempt)
                continue
            if r.status_code in (401, 403):
                raise BlockedError(f"{r.status_code} from {url}; not retrying")
            if r.status_code == 429 or r.status_code >= 500:
                if attempt == self.max_retries:
                    r.raise_for_status()
                retry_after = r.headers.get("Retry-After", "")
                time.sleep(float(retry_after) if retry_after.isdigit() else self.backoff_s * 2**attempt)
                continue
            r.raise_for_status()
            return r
        raise AssertionError("unreachable")


def _slug(text: str, n: int = 60) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:n] or "x"


def save_raw(source: str, content: bytes, url: str, params: dict | None = None, ext: str = "bin",
             label: str = "", fetched_at: datetime | None = None) -> RawSnapshot:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    digest = hashlib.sha256(content).hexdigest()
    rel = Path("raw") / source / fetched_at.strftime("%Y-%m-%d") / f"{_slug(label or url)}_{digest[:12]}.{ext}"
    path = data_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    meta = {"source": source, "url": url, "params": params or {}, "fetched_at": fetched_at.isoformat(),
            "sha256": digest, "path": rel.as_posix()}
    path.with_name(path.name + ".meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return RawSnapshot(source=source, fetched_at=fetched_at, path=rel.as_posix(), sha256=digest,
                       params=params or {}, url=url)


def read_raw(snap: RawSnapshot) -> bytes:
    p = Path(snap.path)
    return (p if p.is_absolute() else data_root() / p).read_bytes()


def load_snapshots(source: str, root: Path | None = None) -> list[RawSnapshot]:
    """Rebuild snapshot records from sidecars, so parsers can rerun without refetching."""
    base = (root or data_root()) / "raw" / source
    snaps = []
    for meta_path in sorted(base.glob("*/*.meta.json")):
        m = json.loads(meta_path.read_text(encoding="utf-8"))
        snaps.append(RawSnapshot(source=m["source"], fetched_at=datetime.fromisoformat(m["fetched_at"]),
                                 path=m["path"], sha256=m["sha256"], params=m["params"], url=m["url"]))
    return snaps


def snapshot_ref(snap: RawSnapshot) -> str:
    """source_ref for anything parsed from a snapshot: the URL plus the raw file."""
    return f"{snap.url} | raw:{snap.path}"
