# Sealed forecasts

Each forecast is written to `forecasts/sealed/` as canonical JSON and identified by its SHA-256.
A hash proves nothing about *when* until it is timestamped independently. Each sealed file has an
OpenTimestamps proof beside it (`<file>.ots`), which anchors its SHA-256 in the Bitcoin blockchain
via public calendar servers. Nobody has to trust us.

- **Verify the hash:** `python -c "from engine.sealing import verify; print(verify('<path>'))"`
- **Verify the timestamp:** drop the `.json` and `.ots` files on https://opentimestamps.org, or run
  `python scripts/ots.py info <file>.ots`. `scripts/run_daily.py` upgrades pending proofs to full Bitcoin proofs.

| Sealed (UTC) | Twin | Forecast | Median | 80% range | Vs guidance | Resolves | SHA-256 |
|---|---|---|---|---|---|---|---|
| 2026-10-02 20:58 | DAL | 2026Q3 revenue growth, yoy % (GAAP) | 15.2 | 10.6 to 19.9 | guidance mid-teens (15.0); P(above) 52% | Delta Q3 release, ~Oct 9 | `f6892ab9366122fd81b64c1106b052c1962638c6ab8644587c5baee2d2058bd8` (OpenTimestamps submitted 2026-10-02 21:13 UTC) |
| planned ~2026-10-27 | CMG | 2026Q3 comps, revenue growth, margin | | | | Oct 28 after close | |

Outcomes are recorded here after the release, unchanged rows above, with the reported value and its SEC accession.
