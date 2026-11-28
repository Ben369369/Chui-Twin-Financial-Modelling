"""Analyst consensus, archived daily so a point-in-time history builds up from now on.

Consensus estimates are licensed data, and history of what the consensus *was* on a given day cannot be
bought back cheaply later. So every configured provider's response is saved untouched, once a day per
ticker, under data/raw/<source>/<YYYY-MM-DD>/ (data/ is gitignored and never published). The fetch time
is the point in time: a snapshot is evidence of the consensus as of `fetched_at`, nothing earlier.

Parsing into ExternalForecast rows (source "consensus") is written per provider against real saved
responses, not against documentation, and can be rerun over the whole archive at any time.

A provider is active only when its API key environment variable is set. Keys never reach the raw files,
their metadata, or log output.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from adapters.http import PoliteClient, save_raw
from engine.observation import RawSnapshot


@dataclass(frozen=True)
class ConsensusProvider:
    name: str            # source name for raw storage, e.g. "consensus_fmp"
    key_env: str         # environment variable holding the API key
    url: str             # endpoint, without credentials
    params: dict         # fixed query parameters; "{ticker}" in a value is filled in per request
    key_param: str       # query parameter that carries the key
    min_interval_s: float = 1.0

    def api_key(self) -> str | None:
        return os.environ.get(self.key_env) or None


PROVIDERS = {
    # Financial Modeling Prep, stable "analyst estimates" endpoint (quarterly). Personal-use plans only:
    # research use, no redistribution. Terms to be confirmed by the owner before the key is set.
    "fmp": ConsensusProvider(
        name="consensus_fmp",
        key_env="CHUI_FMP_API_KEY",
        url="https://financialmodelingprep.com/stable/analyst-estimates",
        params={"symbol": "{ticker}", "period": "quarter", "page": "0", "limit": "12"},
        key_param="apikey",
    ),
}


def redact(text: str, secret: str | None) -> str:
    return text.replace(secret, "***") if secret else text


def active_providers(providers: dict[str, ConsensusProvider] = PROVIDERS) -> list[ConsensusProvider]:
    return [p for p in providers.values() if p.api_key()]


def fetch_snapshot(provider: ConsensusProvider, ticker: str, client: PoliteClient) -> RawSnapshot:
    """One raw snapshot of the provider's consensus for one ticker. The key is sent but never stored."""
    key = provider.api_key()
    if not key:
        raise RuntimeError(f"{provider.key_env} is not set")
    query = {k: v.replace("{ticker}", ticker) for k, v in provider.params.items()}
    try:
        r = client.get(provider.url, params={**query, provider.key_param: key})
    except Exception as e:  # error messages from requests contain the full URL, key included
        raise RuntimeError(redact(f"{type(e).__name__}: {e}", key)) from None
    if key in r.text:
        raise RuntimeError("response echoes the API key; not saved")
    return save_raw(provider.name, r.content, provider.url,
                    params={"ticker": ticker, **query, "kind": "consensus"},
                    ext="json", label=f"{ticker}_{provider.name}")
