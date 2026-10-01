"""Period labels ("2024Q3", "2024-07") and calendar arithmetic."""

from __future__ import annotations

import re
from datetime import date, timedelta

_Q = re.compile(r"^(\d{4})Q([1-4])$")
_M = re.compile(r"^(\d{4})-(\d{2})$")

FREQUENCIES = ("quarter", "month")


def period_of(d: date, freq: str) -> str:
    if freq == "quarter":
        return f"{d.year}Q{(d.month - 1) // 3 + 1}"
    if freq == "month":
        return f"{d.year}-{d.month:02d}"
    raise ValueError(f"unknown frequency {freq!r}")


def _index(p: str) -> tuple[str, int]:
    if m := _Q.match(p):
        return "quarter", int(m[1]) * 4 + int(m[2]) - 1
    if m := _M.match(p):
        return "month", int(m[1]) * 12 + int(m[2]) - 1
    raise ValueError(f"bad period label {p!r}")


def _label(freq: str, idx: int) -> str:
    if freq == "quarter":
        return f"{idx // 4}Q{idx % 4 + 1}"
    return f"{idx // 12}-{idx % 12 + 1:02d}"


def shift(p: str, n: int) -> str:
    freq, idx = _index(p)
    return _label(freq, idx + n)


def diff(a: str, b: str) -> int:
    """Number of periods from b to a (a - b)."""
    fa, ia = _index(a)
    fb, ib = _index(b)
    if fa != fb:
        raise ValueError("cannot diff periods of different frequency")
    return ia - ib


def periods_per_year(freq: str) -> int:
    return {"quarter": 4, "month": 12}[freq]


def _start(freq: str, idx: int) -> date:
    if freq == "quarter":
        y, q = divmod(idx, 4)
        return date(y, 3 * q + 1, 1)
    y, m = divmod(idx, 12)
    return date(y, m + 1, 1)


def bounds(p: str) -> tuple[date, date]:
    freq, idx = _index(p)
    return _start(freq, idx), _start(freq, idx + 1) - timedelta(days=1)


def span(first: str, last: str) -> list[str]:
    n = diff(last, first)
    return [shift(first, i) for i in range(n + 1)] if n >= 0 else []
