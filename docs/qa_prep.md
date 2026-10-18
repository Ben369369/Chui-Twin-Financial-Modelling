# Finals Q&A prep (10 minutes)

Short answers first; the evidence line is where to point if they push. Numbers as of the 2026-10-18 rescore.

## Method

**How do you avoid lookahead bias?**
Every observation stores `observed_at` (the period it describes) and `available_at` (when it could first be known),
and the backtest only uses rows with `available_at` before the forecast time. Lags are conservative: monthly
macro data counts as known 45 days after month end, XBRL facts the day after filing, guidance from the release's
EDGAR acceptance time. *Evidence:* `tests/test_point_in_time.py`, `provenance.md` (available_at column).
*The caveat to volunteer:* model structure (which signals, which KPIs) was chosen with today's knowledge. The
clean tests are the 14 rules-only factory twins, which use untuned industry defaults, and the sealed forecasts.

**Why such a simple model? Why not ML?**
About 26–31 scored quarters per KPI. A complex model would fit noise. The engine is a precision-weighted state
estimate plus Bayesian regression with priors from the causal graph; differences in skill under ~0.05 are noise.

**Where do the causal edges come from?**
Priors set before looking at outcomes, in standardized units ("one sd of demand moves revenue growth by 0.6 sd"),
then calibrated by Bayesian regression on each twin's history. They are validated, not discovered. *Evidence:*
`docs/model.md` §3.

**What is CRPS and why use it?**
Continuous ranked probability score: it scores the whole forecast distribution, so a forecast is rewarded for a
range that is both centered and appropriately narrow. For a point forecast it reduces to absolute error. Skill =
1 − CRPS(twin)/CRPS(baseline); positive means the twin wins.

## Results

**Why does the twin only tie naive on restaurant and hotel revenue?**
Free public data carries little company-specific signal there: national restaurant sales and CPI describe the
industry, not Chipotle. Airlines are strongest because TSA checkpoint counts and jet fuel are direct, timely
sensors. Every twin publishes its own score so users can see which to trust.

**Why do analysts beat you on Chipotle?**
They have information free data doesn't (management access, card-spend panels, channel checks). Over 6 quarters,
consensus wins (skill −0.37). We beat management guidance on Chipotle comps (+0.31, 20 quarters) and on Delta
revenue (+0.29, 14 quarters). The honest pitch: matching guidance-level accuracy across many companies cheaply,
not beating the sell side on one.

**Tell me about the Delta miss.**
Sealed median 15.2% revenue growth, actual 21.1%, outside the 80% range. GAAP revenue includes third-party refinery
sales, which rose 76% with fuel prices (+~6.7 points). Delta's guidance, which the twin anchors on, excludes the
refinery; on that basis growth was 15.7%, 0.5 points from the median. Lesson: match each anchor's definition to
its KPI. The margin forecast was a hit (6.9 vs 7.2). The miss stays as scored. *Evidence:* `docs/sealed_results.md`.

**What drives the Chipotle forecast?**
The largest driver is a sharp drop in Chipotle news tone in July–August 2026 (sentiment −1.16 sd), which pulls
transactions and comps down. GDELT has no Chipotle tone for 11 days of Q3, so the state rests on 81 of 92 days;
that is written next to the seal. The model is not changed after the fact.

What was in the news (checked 2026-10-18):
1. **Cyclospora, late July (industry-wide, not Chipotle's).** On the Q2 call (Jul 29) the CFO said sales softened by
   "about 200 basis points" in the second half of July around an industry cyclospora outbreak; the CEO said Chipotle
   was not involved (implicated products not on its menu). Declared over Sep 11.
2. **Salmonella from jalapeños, August (Chipotle's own).** On Aug 4 Minnesota officials tied a salmonella outbreak
   to jalapeños served at Chipotle; the stock fell 9.7% that day. Chipotle pulled the jalapeños. Final FDA/CDC count:
   488 ill in 34 states, 65 hospitalized, no deaths, onsets Jun 16–Aug 26; clusters at Chipotle and QDOBA; source a
   Sinaloa grower via Coast Citrus Distributors. Declared over Oct 2.

**Did management guide Q3?** Yes, on the call, not in the press release: comps "somewhere around a plus 1%",
assuming the ~200 bp cyclospora drag lasts the whole quarter (underlying trend ~3%). The twin only reads guidance
from earnings releases, so it anchored on 2.65%, the midpoint implied by the full-year "low single digit" range,
and its sealed median (2.94%) sits about 2 points above management's call guide. Two honest consequences:
(a) the guidance comparison in the seal is against the release, not the call; (b) the August salmonella outbreak
came after the call guide, so management's +1% did not include it, while the twin's sentiment state did. Say this
plainly if asked; reading call transcripts for guidance is a known gap and a roadmap item.

**Your intervals: are they calibrated?**
Unevenly. Some twins are too wide (80% coverage of 1.00), Delta revenue a little narrow (0.67). Recalibrating
interval width per twin is on the list.

## Scale and onboarding

**What would 500 tickers take?**
The engine and adapters already handle any company; a twin costs one spec file. The factory builds one in ~2
minutes (RCL: 103 s, mostly waiting on rate limits) for about $0.20–0.35 of LLM tokens. The real limits:
(1) industry packs: today 5 packs cover restaurants, airlines, hotels, homebuilders and general retail, and the LLM
maps uncovered SIC codes to the nearest one; more industries need more packs and their shared data series;
(2) GDELT rate limits for news tone, which is why fetches retry daily; (3) company-specific signal quality, which
the scorecard measures per twin.

**How do you stop the LLM from hallucinating?**
The model proposes; code decides. Every proposal must carry a quote copied from the 10-K, and code drops it if the
quote isn't in the filing, the series can't be fetched, the XBRL concept lacks recent history, or the state or KPI
doesn't exist. Every proposal and every rejection reason is saved in `<ticker>.onboarding.json`; the raw prompt and
response under `data/raw/llm/`.

**Did the LLM make forecasts better?**
No, not on the shared KPIs: on UAL, MAR, SBUX and TGT, skill moved by ±0.03 (MAR revenue slightly worse). Its value
is coverage (companies no pack covers) and new KPIs: United's fuel and labor share of revenue, Target's SG&A and
cost-of-sales ratios, all beating naive. *Evidence:* `docs/experiments.md` §2.

**Does the engine really have no company code?**
Yes, and two tests enforce it: one scans `engine/` for tickers, state names and series prefixes; another runs
estimation and simulation end to end on a dummy template with made-up state names.

## Data and trust

**Is the data legal?**
Public sources only, no logins, robots.txt and terms checked and logged in `provenance.md`. One judgment call to
own: Chipotle's site terms say "personal, noncommercial use". We store only a count of public store and job URLs
from its sitemaps, never republish the pages, and recorded that as an accepted risk on 2026-10-01.

**How do I know the sealed forecast wasn't made after the fact?**
The forecast file's SHA-256 is anchored in the Bitcoin blockchain via OpenTimestamps (Delta: block 969637, Oct 2).
Anyone can drop the `.json` and `.ots` files on opentimestamps.org. `scripts/resolve_sealed.py` re-checks the hash
and accepts an outcome only if it became public after the seal.

**How do you validate extracted numbers?**
Automatic checks on all 2,564 reported values (0 failures): text spans must appear verbatim in the saved filing,
comps = transactions + check, physical bounds, and outliers over 4 sd flagged (24, all real events such as COVID).
A random sample goes to manual review. *Evidence:* `docs/validation_report.md`.

## Product

**Who would use this?**
Buy-side analysts and risk teams who cover many names and want a cheap, scored, explainable first read between
reports, plus scenario questions ("jet fuel +30%: who is exposed?"). It is a starting point next to analyst work,
not a replacement for it.

**What would you do with more time or money?**
Company-level signals where industry data is too coarse (postings, foot traffic, card spend if licensed); turn
the LLM's suggested operating metrics (comps, RevPAR, occupancy) into checked extraction rules; the bank template;
more sealed forecasts to grow the out-of-sample record.
