# Data provenance

Every source the system touches. Checked on the date shown. Raw responses are stored under
`data/raw/<source>/<YYYY-MM-DD>/` with a `.meta.json` sidecar (URL, params, fetch time, SHA-256).

| Source | Access | License / terms | Informs | available_at rule | Checked |
|---|---|---|---|---|---|
| SEC EDGAR submissions, filing documents (8-K EX-99.x) | `data.sec.gov`, `www.sec.gov/Archives`; User-Agent with name + email (env `CHUI_SEC_USER_AGENT`); ≤5 req/s | US government public data; SEC fair-access policy (declared UA, ≤10 req/s) | Ground truth from earnings releases (CMG comps, transactions, check, restaurant-level margin) | EDGAR acceptance timestamp (UTC) | 2026-09-30 |
| SEC XBRL company facts | `data.sec.gov/api/xbrl/companyfacts` | Same as above | Ground truth from GAAP facts (DAL revenue growth, operating margin) | Filing date + 1 day (companyfacts has no acceptance time; conservative) | 2026-09-30 |
| FRED | `fred.stlouisfed.org/graph/fredgraph.csv` (no key) | St. Louis Fed terms: free use with attribution; series used here originate from BLS, Census and EIA (public domain) | Macro demand (Census MRTS food services `RSFSDP`), prices (CPI food away from home `CUSR0000SEFV`, CPI airline fares `CUSR0000SETG01`), input costs (BLS average prices ground beef `APU0000703112`, chicken `APU0000706111`; EIA Gulf Coast jet fuel `DJFUELUSGULF`) | Period end + conservative lag: daily 2d, weekly 7d, monthly 45d, quarterly 100d | 2026-09-30 |
| BLS Public Data API v2 | `api.bls.gov/publicAPI/v2` (no key: 25 queries/day, 10 years/query) | US government public domain | Labor (avg hourly earnings: food services `CES7072200003`, air transportation `CES4348100003`) | Month end + 40d | 2026-09-30 |
| Wikimedia Pageviews API | `wikimedia.org/api/rest_v1/metrics/pageviews` | Data CC0; API asks for a descriptive User-Agent | Attention on company articles (demand, low confidence) | Day + 2d | 2026-09-30 |
| TSA checkpoint travel numbers | `www.tsa.gov/travel/passenger-volumes[/<year>]` HTML table | US government public information. robots.txt disallows only `/core/`, `/profiles/`, `README.md` | Airline demand | Day + 2d | 2026-09-30 |

## Point-in-time caveats (known, not yet fixed)

- **Revisions.** FRED and BLS return the latest vintage. Historical values in a backtest may include revisions published after `as_of` (CES earnings are revised twice; MRTS retail sales annually). Fix: ALFRED vintages (free FRED API key). Market series (jet fuel) and counts (TSA, Wikimedia) are not revised in practice.
- **Release dates are approximated** by conservative lags, not taken from release calendars. Conservative lags can only hide information, never leak it.
- **XBRL ground truth is dated at the 10-Q/10-K filing**, about two weeks after the earnings press release. Backtest forecasts for those KPIs are therefore made slightly later than they could be. This loses no information and leaks nothing.

## Sources reviewed but not used yet

| Source | Status | Reason |
|---|---|---|
| chipotle.com (menu prices), locations.chipotle.com (store locator) | **On hold, needs a decision** | robots.txt allows crawling (only `/error-page` disallowed). Terms of Use limit use to "personal, noncommercial use" and say users "will not copy or distribute any part of the Services" without written consent. There is no explicit scraping clause. Collecting facts (prices, store counts) for research is a gray area. |
| jobs.chipotle.com (careers) | **On hold** | robots.txt disallows `/search-jobs/`, the obvious listing path. Any scraper must avoid it. |
| Google Trends | Not built | No public API. `pytrends` is an unofficial client and automated querying conflicts with Google's terms. An official Trends API alpha exists with gated access. |
| Consensus estimates (FactSet, Visible Alpha, etc.) | Not available | Licensed data. A legal substitute is needed: hand-entered from public press coverage with source_ref, or dropped as a baseline. |
| EIA API, USDA AMS MARS | Planned | Free, but each needs a registered API key. |
