# Chui Twin: Live Demo Script

Slide 13 of the finals deck, 12 minutes inside the 30-minute talk. Every click below was tested on Oct 19–20, 2026.
Numbers move a little as new data arrives each morning, so read them off the screen; the ones here tell you what
to expect.

**How to read this script**

- **Do:** what to click or type.
- **Say:** lines to say out loud, close to word for word.
- **Explain:** what is on screen, in plain words, if the room needs it.
- **Expect:** the numbers you should see.
- **If asked:** answers to have ready. Don't raise these yourself.

| Clock | Step | Time |
|---|---|---|
| 0:00 | 1. The portfolio | 90 s |
| 1:30 | 2. Start a new company (live) | 30 s |
| 2:00 | 3. One shock, every airline | 2 min |
| 4:00 | 4. Inside Delta | 3 min |
| 7:00 | 5. The new company is ready | 2 min |
| 9:00 | 6. Ask the twin | 2 min |
| 11:00 | 7. The open bet | 1 min |
| 12:00 | Back to the deck, slide 14 | |

---

## Before you present (30 minutes before)

1. **Terminal 1**, in the project folder: `python -m uvicorn api.serve:app --port 8000`. Leave it running. It
   prints `Uvicorn running on http://127.0.0.1:8000`.
2. **Browser tabs**, each clicked once so they load fast:
   http://localhost:8000/#/portfolio · http://localhost:8000/#/twin/DAL · http://localhost:8000/#/twin/CMG ·
   http://localhost:8000/#/twin/CCL. A last tab with `docs/sealed_forecasts.md` (GitHub or the editor).
3. **Chat check:** http://localhost:8000/api/chat/status shows `"configured": true`.
4. **Terminal 2:** type `python scripts/make_twin.py RCL --llm` and **do not press Enter**. Make sure no
   `specs/auto/rcl.*` files exist, so the live run builds Royal Caribbean fresh.
5. **Backup video** open and ready to play. **Phone hotspot** ready in case the venue wifi blocks the APIs.

---

## Step 1 · 0:00 · The portfolio (90 s)

**Do:** Portfolio tab.

**Say:**
> "Seventeen twins, one engine. Every row was scored the same way: walk-forward from 2017, refit at each earnings
> release using only data public at that moment."

**Explain:** the dot chart shows each KPI's skill against "same as last quarter". Dots right of zero beat it. The
table below has every twin, its industry, who built it (hand, factory or factory + LLM), and its scores.

**Do:** point at the airlines.

**Say:**
> "Airlines are strongest: TSA counts and jet fuel are direct, timely sensors. Every twin shows its own
> reliability, so you always know how far to trust it."

**If asked where it is weak:** "Restaurant and hotel revenue roughly tie last quarter: free public data says
little about one chain's sales. Their margins still beat naive."

---

## Step 2 · 1:30 · Start a new company (30 s)

**Do:** switch to terminal 2 and press **Enter** on the prepared command.

**Say:**
> "While we look at other things, the system is reading Royal Caribbean's annual report for the first time. No
> industry pack covers cruise lines. We'll come back to it in a few minutes."

**Do:** switch back to the browser straight away. Don't wait for it.

---

## Step 3 · 2:00 · One shock, every airline (2 min)

**Do:** on Portfolio, in the **Economy shock** card, click **Jet fuel +30%**.

**Expect:** next-quarter operating margin about Delta −1.8, Southwest −1.6, United −1.4, American −1.4,
Carnival −1.0 points; revenue growth up 0.2–0.6 points.

**Say:**
> "Move one shared series, and every exposed twin responds through its own calibrated model. Jet fuel up 30% cuts
> next-quarter operating margin across all four airlines, while revenue edges up as fares pass the cost on.
> Carnival responds too: the LLM found fuel in its 10-K."

**Explain:** this is one input moved, not five separate models tuned by hand. Each twin translates the move into
its own hidden "input cost" state, then into its KPIs.

**Do:** click **Restaurant sales −5%**.

**Expect:** revenue growth about Darden −4.0, Texas Roadhouse −3.6, Starbucks −3.2, McDonald's −2.4,
Chipotle −1.1.

**Say:**
> "Same idea for restaurants: a 5% drop in restaurant sales nationwide, and every chain responds by its own
> sensitivity."

---

## Step 4 · 4:00 · Inside Delta (3 min)

**Do:** open the **DAL** tab.

**Say:**
> "This is Delta's twin. Revenue growth for the December quarter: a median of about 22%, with an 80% range of
> roughly 17 to 27. On October 9, Delta guided about 20%. The twin, built only from public signals, puts that
> inside its range, a couple of points above."

**Don't point at a guidance diamond or the "Versus expectations" panel on Delta.** Delta's Q4 guide was worded
"approximately 20 percent", which the guidance reader doesn't parse yet, so neither appears for Q4. The 20% above
is from the Oct 9 press release (8-K 0000027904-26-000035).

**Explain** (only what the room needs):
- **The band:** the middle line is the median of 10,000 simulated paths; the shaded area is where 80% of them
  land.
- **Driver bars ("What moves revenue growth"):** the forecast is last quarter's reported growth (21.07) plus a
  small learned drift (+1.28) plus each signal's change since the last report. Every bar is under 0.3 points
  (airfare inflation cooling −0.29, news tone −0.15, Wikipedia and TSA about zero), so the signals say "about like
  last quarter".
- **Hidden states:** demand, capacity, price, input cost, labor and sentiment, estimated each quarter.

**If asked why the twin starts from last quarter rather than Delta's guide:** "It anchors on guidance when it can
read it. Delta's Q4 guide was worded 'approximately 20 percent', which our reader doesn't parse yet, so it falls
back to last quarter's number. The fix is one rule in the spec, and it's on the list."

**If asked whether 22% is too high, since Q3 included refinery sales:** "Fair point. Q3's 21% included
third-party refinery revenue that Delta's own guide excludes. That's the same definition gap behind our sealed
Q3 revenue miss on slide 11. The lesson we recorded is to match each anchor's definition to its KPI; the next step
is a revenue KPI that excludes refinery sales, like Delta's own guide."

**Do:** click one **driver bar** (TSA or jet fuel) to open its sources.

**Say:**
> "Every bar is one data series, and every number traces back to a file we saved before parsing it."

**Do:** in the **Scenario** panel, click the preset **Fuel / commodity spike**.

**Expect:** operating margin about −7.5 points, revenue about +0.7. It is a 2 sd shock, bigger than the +30%
button.

**Say:**
> "Scenarios fade at speeds measured from real events. Delta's IT outage was gone in a quarter; Chipotle's
> food-safety crisis lasted years."

---

## Step 5 · 7:00 · The new company is ready (2 min)

**Do:** back to terminal 2. Read the summary line: the pack it chose, drivers added, KPIs, rejected proposals,
tokens. (Rehearsals took 55–103 seconds and chose the hotels pack, with jet fuel and airfares as drivers.)

**Say:**
> "It picked an industry pack and added drivers, and every proposal came with a quote from the filing. Anything
> whose quote isn't in the 10-K, or whose data can't be fetched, was dropped by code, not by the model."

**Do:** open `specs/auto/rcl.onboarding.json` and show one accepted quote. If there are rejections, show one with
its reason. If there are **none**, open `specs/auto/ccl.onboarding.json` and show a Carnival rejection instead
(an edge dropped because "quote not found in the 10-K"). Then refresh the browser and open `#/twin/RCL`.

**Say:**
> "Two minutes from ticker to a scored twin, for a company the system had never seen."

**If asked whether the LLM improves accuracy:** "Not on the KPIs the twins already had. What it adds is coverage,
and new KPIs like United's fuel share of revenue, which the twin forecasts better than naive."

**If someone points at a weak new KPI** (in a rehearsal it added `fuel_pct_revenue`, built from total cost of
goods, skill −0.52): "The model named it fuel share but built it from total cost of goods, and it forecasts worse
than naive. That's why new KPIs stay out of the portfolio until a person checks them."

---

## Step 6 · 9:00 · Ask the twin (2 min)

**Do:** open the **chat panel** and type:
> What happens to airlines if jet fuel rises 30%?

It takes **15–20 seconds**. Fill the wait:
> "It's calling the same API you just saw. It doesn't answer from memory."

**Expect:** a table of the same five numbers as the jet-fuel button in step 3, plus a note that the results are
what the calibrated model implies.

**Say:**
> "Same numbers as the button, because it is running the same twin. Every number in that answer comes from a tool
> call, with its source."

**Don't ask on stage:** "What happens to Chipotle if a food-safety scare hits?" It works, but the answer is long:
it says it re-ran with a different start quarter, and revenue moves far more than comps. Save it for Q&A if
someone wants to try their own question.

---

## Step 7 · 11:00 · The open bet (1 min)

**Do:** open the **CMG** tab, then the sealed-forecasts tab.

**Say:**
> "Chipotle's third-quarter forecast was sealed on Sunday, October 18, and anchored in Bitcoin. It resolves on
> October 28, a week after today. Delta's resolved on October 9: margin inside the range, revenue above it, as on
> slide 11."

**Do:** back to the deck, **slide 14**.

---

## Avoid on stage

These all work, but each gives a sharp judge an easy target:

- **Beef prices +20%:** moves Starbucks' margin −2.8 points. A coffee chain hurt by beef invites a laugh.
- **Air travel −10%:** revenue moves only 0.2–0.6 points. Looks weak.
- **Chipotle + Demand slump:** revenue −16 against comps −3.4. Revenue and comps are calibrated separately, and
  the gap looks wrong.
- **Any airline + Food-safety scare or Wage pressure:** the labels don't fit an airline, and wage pressure
  *raises* airline revenue through the price edge.
- **The Chipotle food-safety chat question** (see step 6).

**If asked why Chipotle's food-safety preset is only −3 comps when slide 14 shows −29.7% in 2015:** "The preset
is a typical scare; 2015 was far bigger. Drag the sentiment slider further to see that scale."

**Safe extras** for spare time or volunteers:
- **Chipotle, Price increase:** check +1.4, transactions −1.3, comps +0.1, restaurant margin +1.0. Price up,
  traffic down, margin up.
- **Chipotle, Food-safety scare:** transactions −3.0, comps −3.0, restaurant margin −1.8.

---

## If something breaks

- **Blank page:** the server isn't running. Rerun `python -m uvicorn api.serve:app --port 8000`.
- **Port 8000 taken:** use `--port 8001` and http://localhost:8001.
- **Live onboarding fails** (SEC slow, Anthropic error): say "the SEC is slow today", and show
  `specs/auto/ccl.onboarding.json` instead. A GDELT 429 line in the output is expected and harmless.
- **A twin errors:** switch to DAL or UAL, the most robust.
- **Chat unavailable:** skip step 6 and give the time to step 7 or questions.
- **No internet:** switch to the phone hotspot. If that fails too, play the backup video.
- **Everything fails:** play the backup video.

---

## Hand-over: Longaeva volunteers try it themselves

The finals include "real-world testing with Longaeva investment team volunteers". Hand them the laptop on the
**Portfolio** page, with the dashboard running and terminal 2 open. Offer these, about 2 minutes each:

1. **Open any twin and run a scenario.** Click a preset or drag a state slider; the band and the *Scenario impact*
   bars move. Click a driver bar to see its data.
2. **Economy shock.** *Jet fuel +30%* or *Restaurant sales −5%*.
3. **Ask the twin.** Any question in plain words. Every number comes from a tool call on the twin.
4. **Build a company of their choice:** `python scripts/make_twin.py <TICKER>` (1–2 minutes), then refresh and
   open `#/twin/<TICKER>`.

**Tickers that build** (SEC industry codes checked Oct 19): restaurants YUM, WING; airlines JBLU, ALK; hotels H,
WH; homebuilders TOL, NVR; general retail DG, DLTR, COST, M. Avoid recent IPOs such as CAVA (2023): too few
quarters to score. Use `--llm` only for a company no pack covers that is still driven by operations (cruise
lines); each run costs about $0.20–0.40.

**When they pick something outside the system** (a bank, a biotech, a chip maker), let it refuse. It prints one
line, for example `[JPM] NOT COVERED: no industry pack covers SIC 6021`. With `--llm`, the model reads the 10-K and
agrees that no pack fits a diversified bank. Say: "It's built for businesses driven by observable operations. It
refuses rather than inventing a model. Banks need their own template, and that's on the roadmap."

**Don't:** close terminal 1; run `--llm` on many tickers; promise a new twin's accuracy before its scores print.
