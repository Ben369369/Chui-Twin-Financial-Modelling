# Presenter briefing: Chui Twin, end to end

For Benedict, before the finals on Wednesday, Oct 21, 2026 (4:30–6:00 p.m. ET; 30 minutes of talk and demo, then
10 minutes of Q&A). Everything here comes from the repo as of Oct 18. Companion files: the deck (link in chat),
`docs/demo_script.md` (the 12-minute demo), `docs/qa_prep.md` (likely questions).

---

## 0. Opening the dashboard

**Start it (once, about 30 minutes before you present):**

1. Open a terminal in the project folder:
   `C:\Users\benon\OneDrive - Princeton University\Desktop\Chui Twin Longaeva Hackathon Financial modelling`
   (in VS Code: Terminal → New Terminal opens there).
2. Run: `python -m uvicorn api.serve:app --port 8000`
   Leave that terminal open. It prints `Uvicorn running on http://127.0.0.1:8000`. Closing it stops the dashboard.
3. Open a browser at **http://localhost:8000**.

**Direct links** (bookmark them; they work as browser tabs, so you can pre-open each view):

| View | Link |
|---|---|
| Portfolio (all twins, economy shocks) | http://localhost:8000/#/portfolio |
| Delta | http://localhost:8000/#/twin/DAL |
| Chipotle | http://localhost:8000/#/twin/CMG |
| Carnival (LLM-onboarded) | http://localhost:8000/#/twin/CCL |
| Any twin | `http://localhost:8000/#/twin/<TICKER>` |

**Checks before you go on:** http://localhost:8000/api/chat/status should say `"configured": true` (chat needs
`ANTHROPIC_API_KEY`, which is set on this laptop). Click through Portfolio, DAL, CMG and CCL once so they load fast
(each forecast takes about 0.4 s the first time).

**During the talk:** present the deck full screen; at slide 13 switch to the browser (Alt+Tab), run the demo, then
switch back for slide 14. For the live onboarding step you need a second terminal (the first one is busy running
the dashboard) with the command typed in advance: `python scripts/make_twin.py RCL --llm`. After it finishes, the
new twin appears at `#/twin/RCL` after a page refresh.

**If the page is blank:** the server isn't running; rerun step 2. **If port 8000 is taken:** use `--port 8001` and
http://localhost:8001. **If presenting remotely:** share the browser window, not the whole screen, so the terminal
doesn't show.

**What's on screen:**
- **Portfolio:** tiles with the headline numbers; a dot chart "Where the twin beats last quarter" (dots right of
  zero beat naive); the full scorecard table (twin, industry, built by, KPI, errors, skill, coverage); the
  **Economy shock** card with buttons *Jet fuel +30%*, *Restaurant sales −5%*, *Air travel −10%*, *Beef prices +20%*,
  *Restaurant wages +6%*.
- **Twin view:** forecast band per KPI (median and 80% range) with guidance or consensus as a grey diamond;
  **Versus expectations** (the twin's gap to guidance/consensus, probability of beating it); **driver bars** (what
  moves each KPI; click a bar to see its data series and sources); hidden states over time; **Scenario** panel with
  presets *Food-safety scare*, *Fuel / commodity spike*, *Price increase*, *Demand slump*, *Wage pressure*, and
  sliders per state; **Scenario impact on the mean**.
- **Chat panel:** "Ask about a twin or a scenario…". Claude answers with tools over the same API, so every number it
  quotes comes from the twin.

Measured today: *Jet fuel +30%* moves next-quarter operating margin by −1.87 points (Delta), −1.60 (Southwest),
−1.46 (United), −1.43 (American), −1.02 (Carnival), with revenue growth up 0.2–0.6 points through fare pass-through.
Read the numbers off the screen on the day; they move with new data.

---

## 1. The project in one paragraph

Chui Twin turns any public company into a runnable operating model built only from public data. It treats each
public data series (TSA checkpoint counts, jet fuel prices, BLS wages, store counts, news tone, Wikipedia
attention) as a **noisy sensor** of a few **hidden operating states** (demand, capacity, price, input cost, labor,
sentiment, expansion). One shared engine estimates those states every quarter, links them to the KPIs companies
report (revenue growth, margins, comps) through a causal graph, simulates 10,000 paths forward, explains every
forecast by driver and data source, and scores every twin the same way against naive baselines, management
guidance and analyst consensus. The engine contains no company code; a new company is a spec file, and the factory
writes that file from a ticker. Built for the Longaeva AI Hackathon; Chipotle and Delta are the deep examples.

**The three claims you are making:**
1. **It scales:** 17 twins on one engine; 15 built from the ticker alone; a new one in about 2 minutes.
2. **It is measured honestly:** walk-forward, point-in-time scoring; negative results published.
3. **It is verifiable:** live forecasts sealed and timestamped in Bitcoin before the outcome.

---

## 2. Timeline

| Date | Milestone |
|---|---|
| Sep 30 – Oct 1 | Engine, adapters, CMG and DAL twins; twin factory; 16-twin portfolio |
| Oct 2 | DAL Q3 forecast sealed (Bitcoin block 969637) |
| Oct 5–6 | Midpoint check-in with the mentor |
| Oct 9 | Stage 2 submission; Delta reported: margin hit, revenue miss |
| Oct 14 | Selected for finals |
| Oct 18 | LLM onboarding; Carnival twin; CMG Q3 sealed; portfolio rescored (17 twins) |
| Oct 19 | Outside review finds backtest timing bug (results dated at the 10-Q, after the press release); fixed, all twins rescored; alpha section, implementation plan |
| **Oct 20** | **Final submission due** |
| **Oct 21** | **Finals presentation** |
| Oct 28 | Chipotle reports Q3 after the close; the sealed bet resolves |

---

## 3. How the code is organized

| Folder | What it does | Rule it keeps |
|---|---|---|
| `engine/` | Estimation, simulation, attribution, evaluation, sealing. Company-agnostic. | No tickers, state names or series names; two tests enforce it |
| `adapters/` | One module per data source (SEC EDGAR/XBRL, FRED, BLS, TSA, Wikimedia, GDELT, sitemap counter). Fetch, save raw, normalize. | Know nothing about companies or states |
| `templates/operating.yaml` | The industry template: the 7 states, default causal edges with priors, KPI structure | Industry structure lives here, not in code |
| `onboarding/` | `industry_packs.yaml` (signals per industry, by SEC SIC code), `factory.py` (ticker → spec), `llm.py` (LLM reads the 10-K) | The model proposes; code decides |
| `specs/` | `cmg.yaml`, `dal.yaml` hand-built; `specs/auto/*.yaml` factory-built; `<ticker>.onboarding.json` LLM audit trail | One file per company |
| `api/` | FastAPI: forecasts, scenarios, history, scorecard, chat; `serve.py` also serves the dashboard | Read-only |
| `web/` | React dashboard (built into `web/dist`) | |
| `scripts/` | `run_daily.py` (scheduled data job), `make_twin.py`, `forecast.py` (incl. `--seal`), `backtest.py`, `resolve_sealed.py`, `validate_ground_truth.py`, `fill_missing.py` | |
| `storage/`, `migrations/` | SQLite database (`data/chui.sqlite`), portable SQL migrations | |
| `forecasts/sealed/` | Sealed forecasts (`.json`) and their timestamp proofs (`.ots`) | Never edited after sealing |
| `data/raw/` | Every raw response, by source and date (not in git) | Raw first, parse later |
| `docs/` | Model, appendix, scorecard, experiments, validation, sealed forecasts, coverage, this briefing | |

**Daily job:** Windows Task Scheduler runs `scripts/run_daily.cmd` at 7:00 every morning: refreshes all 50+ series,
refreshes ground truth from SEC, retries rate-limited GDELT series, upgrades timestamp proofs. Log: `data/daily.log`.

---

## 4. Data sources

| Source | What it gives | Informs |
|---|---|---|
| SEC EDGAR (8-K earnings releases) | Text of releases: Chipotle comps, transactions, check, restaurant margin; management guidance | Ground truth, guidance |
| SEC XBRL company facts | GAAP revenue, operating income, other facts for any filer | Ground truth for every twin |
| SEC 10-K | Annual report text | LLM onboarding |
| FRED | Census retail and restaurant sales, CPI (food away from home, airfares, lodging), beef and chicken prices, jet fuel, housing starts, mortgage rate, home prices, lumber | Demand, price, input cost |
| BLS | Average hourly earnings by industry | Labor |
| TSA | Daily checkpoint travelers | Airline and hotel demand |
| GDELT | Daily average news tone per company | Sentiment |
| Wikimedia | Daily page views of the company's article (verified by ticker in the infobox) | Demand (low confidence) |
| Chipotle sitemaps + Wayback Machine | US restaurant count, open job postings (counts only) | Capacity, labor |
| Analyst consensus | 6 quarters of Chipotle comps consensus, hand-entered from public news quotes | Consensus baseline |

Scale today: 164,221 observations of 68 series from 6 sources; 2,190 reported KPI values for 17 companies; 56
guidance values; 362 raw snapshots in the database. Every source, its terms and its access method are in
`provenance.md`.

---

## 5. The model, in plain language

Kept simple on purpose: about 26–31 scored quarters per KPI cannot support a complex model.

1. **Signals → features.** Each series becomes a decay-weighted level (each signal has a half-life), then a
   year-over-year change, standardized over the history available at forecast time.
2. **Features → states.** Each state starts at "average" (a N(0,1) prior). Each signal is a noisy reading with
   precision p = c/(1−c) · 0.5^(staleness/half-life), where c is the signal's confidence (0–1). The state is the
   precision-weighted average, so each signal's share of a state is exact and stored.
3. **States → KPIs.** Bayesian linear regression with priors from the causal edges, in standard-deviation units
   ("one sd of demand moves revenue growth by 0.6 sd"). Each KPI is modeled as a **level** (with last-quarter and
   same-quarter-last-year terms), a **change** since the last report, or an **anchored surprise** relative to the
   latest guidance or consensus published before the release.
4. **Identities and bounds.** Accounting identities (comps = transactions + check) are enforced on every simulated
   path; physical bounds (a margin can't exceed 100%) clip the paths.
5. **Simulation.** 10,000 paths in about 0.03 s; states evolve as AR(1) processes, innovations propagate along
   causal edges, scenario shocks decay with a half-life.
6. **Attribution.** A driver waterfall (each bar linked to its data series and raw files) and leave-one-signal-out
   counterfactuals.
7. **Evaluation.** Walk-forward from 2017Q1: at each historical earnings release, refit using only data available
   at that moment, forecast, score. COVID quarters (2020Q1–2021Q4) excluded from scoring; travel twins also exclude
   calibration through 2022Q4. Metric: **CRPS** (scores the whole distribution). **Skill** = 1 − CRPS(twin) /
   CRPS(baseline); positive means the twin wins.

Full math: `docs/model.md`.

---

## 6. The 17 twins

Skill is CRPS skill versus "same as last quarter" (positive = twin better), rescored Oct 19 after the timing fix.

| Twin | Industry pack | Built by | Scored quarters | Skill by KPI |
|---|---|---|---|---|
| CMG Chipotle | restaurant | hand | 30 | transactions +0.19 · check −0.10 · comps +0.21 · restaurant margin −0.07 · revenue growth −0.06 |
| DAL Delta | airline | hand | 27 | revenue growth +0.31 · operating margin +0.36 |
| AAL American | airlines | factory | 26 | revenue growth +0.09 · op margin +0.49 |
| CCL Carnival | hotels | factory + LLM | 27 | revenue growth +0.02 · op margin −0.06 |
| DHI D.R. Horton | homebuilders | factory | 30 | revenue growth +0.13 · pre-tax margin +0.10 |
| DRI Darden | restaurants | factory | 31 | revenue growth −0.01 · op margin +0.10 |
| HLT Hilton | hotels | factory | 26 | revenue growth −0.05 · op margin +0.30 |
| LEN Lennar | homebuilders | factory | 31 | revenue growth −0.06 · op margin +0.18 |
| LUV Southwest | airlines | factory | 26 | revenue growth +0.07 · op margin +0.09 |
| MAR Marriott | hotels | factory | 26 | revenue growth −0.07 · op margin +0.20 |
| MCD McDonald's | restaurants | factory | 30 | revenue growth −0.02 · op margin −0.01 |
| PHM PulteGroup | homebuilders | factory | 27 | revenue growth +0.33 · pre-tax margin +0.68 |
| SBUX Starbucks | restaurants | factory | 29 | revenue growth +0.06 · op margin +0.55 |
| TGT Target | general retail | factory | 31 | revenue growth +0.02 · op margin +0.01 |
| TXRH Texas Roadhouse | restaurants | factory | 29 | revenue growth +0.12 · op margin +0.08 |
| UAL United | airlines | factory | 26 | revenue growth +0.45 · op margin +0.52 |
| WMT Walmart | general retail | factory | 31 | revenue growth 0.00 · op margin +0.15 |

**Patterns** (lead with the first; the rest only if asked): airlines strongest (TSA and jet fuel are direct, timely sensors); margins beat naive
more often than revenue; restaurant and hotel revenue roughly tie naive (little company-specific public signal).

**Hand-built twins in more depth:**
- **Chipotle:** 59 quarters of comps, transactions, check and restaurant-level margin extracted from earnings
  releases, each value with the sentence it came from; store count and job postings from its public sitemaps with
  history from the Internet Archive; news tone; restaurant sales, CPI, beef and chicken prices, restaurant wages;
  guidance from releases; 6 quarters of consensus. Comps anchored on consensus, then guidance.
- **Delta:** GAAP revenue growth and operating margin from XBRL; TSA throughput, jet fuel, airfare CPI, airline
  wages; guidance extracted from releases (worded guidance such as "mid-teens" converted to a range). Revenue
  anchored on guidance.

---

## 7. Results: the numbers to know

| Result | Value |
|---|---|
| KPI series beating **both** naive baselines (the headline) | **24 of 37** |
| KPI series beating "same as last quarter" | **26 of 37** |
| KPI series beating "same quarter last year" | **35 of 37** |
| Factory twins (no tuning) beating "last quarter" | 22 of 30 KPI series (20 beat both) |
| Delta revenue growth vs Delta's guidance | skill **+0.29** (14 quarters), twin better |
| Chipotle comps vs Chipotle's guidance | skill **+0.41** (18 quarters), twin better |
| Chipotle comps vs analyst consensus | skill **−0.37** (6 quarters), consensus better |
| Ground-truth values validated | **2,190**, 0 failures, 23 outliers flagged (all real events) |
| Time to build a new twin | about 100 s (RCL rehearsal: 103 s) |
| LLM cost per twin | about $0.20–0.35 |

Sources: `docs/portfolio_scorecard.md`, `scripts/backtest.py` (expert comparisons), `docs/validation_report.md`.

---

## 8. The sealed forecasts

**How sealing works:** the forecast is written as canonical JSON, its SHA-256 recorded, and the hash submitted to
OpenTimestamps calendar servers, which anchor it in a Bitcoin block within hours. Anyone can verify the file existed
before a date by dropping the `.json` and `.ots` files on opentimestamps.org. `scripts/resolve_sealed.py` rechecks
the hash and accepts an outcome only if it became public after the seal.

**Delta Q3 2026 (sealed Oct 2, resolved Oct 9):**

| KPI | Sealed median (80% range) | Actual | Verdict |
|---|---|---|---|
| Operating margin | 6.9 (−1.8 to 15.6) | 7.2 | Hit: inside the range, beat both naive baselines |
| Revenue growth | 15.2 (10.6 to 19.9) | 21.1 | Miss: above the range; lost to "last quarter" |

Why the miss: GAAP revenue includes third-party refinery sales, which rose 76% with fuel prices (+~6.7 points).
Delta's guidance, the twin's anchor, excludes the refinery; on that basis growth was 15.7%, 0.5 points from the
median. Lesson recorded: match each anchor's definition to its KPI. The scored result stays as sealed.

**Chipotle Q3 2026 (sealed Oct 18, 19:00 UTC; resolves Oct 28 after the close):**

| KPI | Median | 80% range |
|---|---|---|
| Comps | +2.94% | 0.64 to 5.15 |
| Transactions | +1.71% | −0.75 to 4.12 |
| Average check | +1.24% | 0.05 to 2.41 |
| Restaurant-level margin | 25.43% | 20.97 to 29.97 |
| Revenue growth | 9.53% | −0.01 to 19.15 |

SHA-256 `fabe5e811fcf5fe2e0b909a5d7c7e6ff5e69a8ee691645214ec7e816c0016282`.

**Context you must have for the Chipotle bet:**
- **What drives it:** news tone on Chipotle fell sharply in July–August (sentiment state −1.16 sd), pulling
  transactions down about 1.5 points and comps about 0.6. GDELT has no Chipotle tone for 11 days of Q3 (Jul 1–4,
  Sep 14–19, Sep 26), so the state rests on 81 of 92 days; recorded next to the seal.
- **Why the tone fell:** (1) an industry **cyclospora** outbreak in late July that Chipotle said it was not part of,
  but which cut its sales by "about 200 basis points" in the second half of July; (2) a **salmonella outbreak traced
  to jalapeños served at Chipotle** (and QDOBA), public on Aug 4 (stock −9.7% that day): 488 ill in 34 states, 65
  hospitalized, no deaths; declared over Oct 2.
- **Management's Q3 guide:** on the Jul 29 call, comps "somewhere around a plus 1%", assuming the cyclospora drag
  lasts the whole quarter (underlying ~3%). The twin reads guidance only from press releases, so it compared itself
  with 2.65% (the midpoint implied by the full-year "low single digit" range). Its median (2.94%) is about **2
  points above management's call guide**. The salmonella outbreak came after the call, so management's +1% did not
  include it; the twin's sentiment state did.
- **How to frame it:** "We don't know the answer, and neither does anyone in this room. The twin is more optimistic
  than management. The proof it was made before October 28 is in the Bitcoin blockchain."

---

## 9. LLM onboarding (new for finals)

`python scripts/make_twin.py <TICKER> --llm`

1. The factory looks the ticker up at the SEC (CIK, name, SIC industry code) and picks an industry pack by SIC.
2. Claude Sonnet 5.5 reads the latest 10-K (about 100–170k tokens) plus a menu: the 7 states, the packs, the data
   series the system can fetch, the KPIs, and the XBRL concepts this company actually reports. It proposes: the pack
   (needed when no pack covers the SIC code), up to 4 extra driver series, up to 2 extra XBRL KPIs, edge strengths,
   and up to 4 operating metrics (suggestions only).
3. **Every proposal must carry a quote copied from the 10-K.** Code drops it if the quote isn't in the filing, the
   series can't be fetched, the XBRL concept has under 16 quarters or stopped being reported, the state or KPI is
   unknown, or a new KPI has no supported edge.
4. Accepted items are merged over the pack defaults; `<ticker>.onboarding.json` records every proposal, its quote,
   and why rejected ones were dropped. Raw prompt and response saved under `data/raw/llm/`.

**Carnival** (SIC 4400, no pack): hotels pack chosen; airfares added as a drag on demand ("Increases in airfares …
reduce demand for cruises"), jet fuel as input cost; suggested occupancy, berth days, fuel per ton,
passengers as operating metrics. **RCL rehearsal:** 103 s, similar choices plus capacity (new ships) → revenue.

**Result, if asked** (`docs/experiments.md` §2): on UAL, MAR, SBUX, TGT the LLM moved shared-KPI skill by ±0.03 (MAR
revenue slightly worse). Value is coverage plus new KPIs that beat naive: United fuel share +0.37, labor share
+0.32; Target SG&A ratio +0.36, cost-of-sales ratio +0.21. On Starbucks it mixed two XBRL concepts of different
scope, so new KPIs need a person's check before entering the portfolio.

---

## 10. Scenarios and the shock library

- **Twin scenarios:** shock a hidden state by N standard deviations from a start quarter with a half-life; the
  shock propagates along causal edges to KPIs. Presets use half-lives measured from real events.
- **Economy shocks:** move one shared series by a percent (e.g., jet fuel +30%); every twin that uses it responds.
- **Measured shocks** (`shocks/library.yaml`, each point traced to SEC filings): Chipotle 2015 food-safety crisis:
  comps −29.7% at the trough one quarter in, half-life ~7.4 quarters, not half-recovered after 8 quarters. Delta
  July 2024 IT outage: revenue −6.1% versus trend in the quarter, recovered the next. COVID on airlines and
  hotels: half-life ~3.9 quarters.
- Scenario results are what the calibrated linear model implies; moves far outside history (e.g., fares +30%,
  about 2.5 sd) are extrapolation, and the dashboard and chat say so.

---

## 11. Why the numbers can be trusted

1. **Traceable:** every observation, ground-truth value and forecast carries a `source_ref` (filing accession and
   exhibit, URL plus quote, or raw file path).
2. **Point in time:** every row has `observed_at` and `available_at`; backtests use only rows available at the
   forecast moment. Lags are conservative (monthly macro +45 days; daily signals available the next day; guidance
   at EDGAR acceptance time). Reported results are dated at the earnings press release (8-K item 2.02). Until Oct
   19 they were dated at the later 10-Q, so some backtest forecasts came after the release; an outside review
   caught it, we fixed it and rescored, and the results barely moved (25 → 26 of 37 beating last quarter).
3. **Raw first:** every fetch is saved untouched before parsing; parsers can be fixed and rerun.
4. **Legal only:** public sources, no logins, robots.txt and terms checked, all logged in `provenance.md`. One
   accepted risk to own: Chipotle's site terms say "personal, noncommercial use"; only URL counts are stored.
5. **Validated:** automatic checks on every reported value (text spans verbatim in the filing, identities, bounds,
   outliers); a random sample for manual review.
6. **Negative results kept:** JOLTS hiring data (no gain, not adopted); LLM onboarding (no accuracy gain on shared
   KPIs). `docs/experiments.md`.
7. **No company code in the engine:** `tests/test_engine_no_company_code.py` and `tests/test_template_agnostic.py`
   (runs the engine on a dummy template with made-up state names).

---

## 12. Limitations (answer when asked; the backup slide after the close has them)

- Consensus beats the twin on Chipotle comps (6 quarters): analysts see information free data doesn't.
- Restaurant and hotel revenue roughly ties naive.
- Interval coverage uneven: some ranges too wide (1.00), Delta revenue a little narrow (0.67).
- Short histories (26–31 scored quarters); skill differences under ~0.05 are noise. Edges validated, not discovered.
- Structure chosen with hindsight (packs, hand-built specs, LLM reading today's 10-K). Clean tests: the 14
  rules-only factory twins and the sealed forecasts.
- Guidance is read from press releases only; guidance given on earnings calls (like Chipotle's Q3 +1%) is missed.
- GDELT rate limits make news tone lag some days; Lennar's operating-margin XBRL ends in 2022.

---

## 13. Roadmap

1. Turn the LLM's suggested operating metrics (comps, RevPAR, occupancy) into checked release-extraction rules; read
   guidance from call transcripts.
2. Company-level labor signals (postings) where industry data is too coarse.
3. More strong-fit industries reusing adapters: cruise lines, trucking, rail.
4. **Bank template:** deposits, loan growth, credit quality, net interest margin, funding cost (FFIEC call reports,
   Fed H.8, HMDA, CFPB complaints).
5. **Event module:** probability and move size for binary catalysts (ClinicalTrials.gov, FDA), sharing attribution
   and evaluation code.

Coverage map: strong fit (restaurants, retail, airlines, hotels, homebuilders, cruise, trucking, rail); good with
new adapters (energy producers, semiconductors, consumer apps, streaming); weak (enterprise software,
conglomerates, large pharma); new template (banks, insurers); new module (clinical-stage biotech).

---

## 14. Glossary

| Term | Meaning |
|---|---|
| Twin | One company's runnable model: a spec plus the shared engine |
| Hidden state | An unobserved operating driver (demand, capacity, price, input cost, labor, sentiment, expansion) estimated from signals |
| Signal | A public data series mapped to a state, with sign, lag, confidence and half-life |
| Spec | `specs/<ticker>.yaml`: the company's template, signals, KPIs, edges, ground-truth rules |
| Template / pack | Industry structure (states, edges, KPIs) / an industry's shared signals, chosen by SIC code |
| SIC code | SEC's Standard Industrial Classification code for a filer |
| XBRL | Machine-readable financial facts every SEC filer publishes |
| Comps | Comparable restaurant sales growth: transactions + average check |
| RLOM | Restaurant-level operating margin |
| Walk-forward | Refit and forecast at each historical release using only data available then |
| Point in time | Each value stamped with when it could first have been known |
| CRPS | Continuous ranked probability score; scores a whole forecast distribution |
| Skill | 1 − CRPS(twin)/CRPS(baseline); positive = twin better |
| 80% coverage | Share of outcomes inside the 80% range (ideal 0.80) |
| Naive / seasonal naive | "Same as last quarter" / "same quarter last year" |
| Anchored surprise | Forecasting the gap to guidance or consensus rather than the level |
| OpenTimestamps | Free protocol that anchors a file's hash in Bitcoin to prove it existed by a date |

---

## 15. Where to find things fast

| Need | File |
|---|---|
| Full method and results | `docs/technical_appendix.md` (PDF: `docs/Chui_Twin_Technical_Appendix.pdf`) |
| Model math | `docs/model.md` |
| Every twin's score | `docs/portfolio_scorecard.md` |
| Sealed forecasts and outcomes | `docs/sealed_forecasts.md`, `docs/sealed_results.md` |
| Experiments, incl. failures | `docs/experiments.md` |
| Data checks | `docs/validation_report.md` |
| Data sources and terms | `provenance.md` |
| Coverage and roadmap | `docs/coverage_and_roadmap.md` |
| Demo steps | `docs/demo_script.md` |
| Likely questions | `docs/qa_prep.md` |
