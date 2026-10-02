"""OpenTimestamps on Windows: anchor a sealed forecast's hash in the Bitcoin blockchain.

    python scripts/ots.py stamp forecasts/sealed/<file>.json     # writes <file>.json.ots
    python scripts/ots.py upgrade forecasts/sealed/<file>.json.ots   # after ~1 day, embeds the Bitcoin proof
    python scripts/ots.py info forecasts/sealed/<file>.json.ots

The stamp proves the file existed at the time the calendar servers saw its hash, without anyone
having to trust us. Anyone can verify the .ots file at https://opentimestamps.org.

python-bitcoinlib looks up OpenSSL with ctypes.util.find_library, which fails on Windows.
This wrapper points it at the OpenSSL DLL that ships with Python, then runs the normal client.
"""

from __future__ import annotations

import ctypes.util
import os
import sys

_dlls = os.path.join(sys.base_prefix, "DLLs")
_original = ctypes.util.find_library


def _find_library(name: str):
    found = _original(name)
    if found is None and name in ("ssl", "libeay32", "crypto"):
        candidate = os.path.join(_dlls, "libcrypto-3.dll")
        if os.path.exists(candidate):
            return candidate
    return found


ctypes.util.find_library = _find_library

from otsclient.args import parse_ots_args  # noqa: E402


def main() -> None:
    args = parse_ots_args(sys.argv[1:])
    args.cmd_func(args)


if __name__ == "__main__":
    main()
