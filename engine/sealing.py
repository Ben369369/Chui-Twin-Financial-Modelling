"""Sealed forecasts: a canonical JSON record plus its SHA-256.

A sealed file is only credible if its hash is published somewhere with an
independent timestamp before the outcome is known (a pushed git commit, a
post to the mentor). The hash alone proves nothing about when it was made.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def canonical_json(record: dict) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)


def seal(record: dict, out_dir: str | Path) -> tuple[Path, str]:
    sealed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    body = dict(record, sealed_at=sealed_at)
    text = canonical_json(body)
    digest = hashlib.sha256(text.encode()).hexdigest()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = sealed_at.replace(":", "").replace("-", "")
    path = out / f"{record.get('ticker', 'twin')}_{stamp}_{digest[:12]}.json"
    path.write_text(text, encoding="utf-8")
    return path, digest


def verify(path: str | Path) -> str:
    """Recompute the digest of a sealed file; compare with the published hash."""
    return hashlib.sha256(Path(path).read_text(encoding="utf-8").encode()).hexdigest()
