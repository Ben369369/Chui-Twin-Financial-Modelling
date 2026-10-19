# Demo script (finals, 12 minutes inside the 30-minute talk)

The demo sits between deck slide 13 ("Let's run it") and slide 14 (shocks). The 5-minute midpoint version is in git
history (`git show a8cc3e1:docs/demo_script.md`).

## Setup (30 minutes before)

1. `uvicorn api.serve:app --port 8000`, open http://localhost:8000, click once through Portfolio, DAL, CMG, CCL so
   everything is warm.
2. A terminal in the repo root with `CHUI_SEC_USER_AGENT` and `ANTHROPIC_API_KEY` set. Type, but do not run:
   `python scripts/make_twin.py <LIVE_TICKER> --llm`
   `<LIVE_TICKER>` = **RCL** (Royal Caribbean). Rehearsed 2026-10-18: 103 s end to end; the model chose the hotels
   pack (no pack covers SIC 4400), added jet fuel ("6.4% of revenue", quantified 10% sensitivity) and airfares, and
   an edge from capacity (new ships) to revenue growth. The live run's choices can differ: read them off the screen.
   Rehearsed again 2026-10-19: 55 s; same pack and drivers, 5 edges, **0 rejected**, and one new KPI named
   `fuel_pct_revenue` that is really built from total cost of goods sold (its description admits it is a proxy).
   It printed skill **−0.52** vs naive, after the code dropped eight COVID quarters above 100% as scope mismatches.
   If that happens live, say it, don't hide it: "The model named this KPI fuel share but built it from total cost
   of goods. It forecasts worse than naive. That is exactly why new KPIs stay out of the portfolio until a person
   checks them." If the run shows 0 rejections, show a rejection from `specs/auto/ccl.onboarding.json` instead.
   Its spec was deleted after the rehearsal so the live run builds it fresh; delete `specs/auto/rcl.*` again if a
   later rehearsal recreates it. Fallback if the run fails: show `specs/auto/ccl.onboarding.json`.
3. Second browser tab: `docs/sealed_forecasts.md` on GitHub or in the editor.
4. Check `GET /chat/status` says the chat is configured.
5. Backup video of this whole demo, recorded Monday, ready to play.

## 0:00 The portfolio (90 s)

**Portfolio view.**
> "Seventeen twins, one engine. Every row was scored the same way: walk-forward from 2017, refit at each earnings
> release using only data public at that moment. Dots right of zero beat 'same as last quarter'."

Point at the airlines, then the restaurants.
> "Airlines are strongest: TSA counts and jet fuel are direct, timely sensors. Restaurant revenue roughly ties naive,
> because free public data says little about one chain. Every twin shows its own reliability."

## 1:30 Start a new company (30 s)

Switch to the terminal, run the prepared `make_twin.py <LIVE_TICKER> --llm`.
> "While we look at other things, the system is reading this company's 10-K for the first time. We'll come back to
> it in a few minutes."

## 2:00 One shock, every airline (2 min)

**Economy shock card.** Click **Jet fuel +30%**.
> "Move one shared series and every exposed twin responds through its own calibrated model. Jet fuel up 30% cuts
> next-quarter operating margin across Delta, United, American and Southwest, while revenue edges up through fare
> pass-through. Carnival responds too: the LLM found fuel in its 10-K."

Read the actual numbers off the screen; do not quote them from memory. Then **Restaurant sales −5%**.

## 4:00 Inside Delta (3 min)

Open **DAL**.
> "Revenue growth with an 80% band. The grey diamond is Delta's own guidance, read out of the press release. The
> twin starts from guidance and forecasts the surprise."

Click a driver bar to show its sources (series, raw file, URL).
> "Every bar is one data series, and every number traces to a file we saved before parsing it."

Apply the **Fuel / commodity spike** preset.
> "Scenarios fade at speeds measured from real events. The Delta outage was gone in a quarter; Chipotle's
> food-safety crisis lasted years."

## 7:00 The new company (2 min)

Back to the terminal. Read the summary line: pack, drivers, KPIs, rejected proposals, tokens.
> "It picked an industry pack, added drivers, and every one came with a quote from the filing. Anything whose quote
> isn't in the 10-K, or whose data can't be fetched, was dropped by code, not by the model."

Open `specs/auto/<live_ticker>.onboarding.json`, show one accepted quote and one rejection reason. Refresh the
dashboard and open the new twin.
> "Two minutes from ticker to a scored twin. Honest result: on existing twins the LLM didn't improve accuracy on
> the shared KPIs. What it adds is coverage."

## 9:00 Ask the twin (2 min)

Open the chat panel. Ask:
> "What happens to Chipotle's comps next quarter if a food-safety scare hits?"

Point out that the assistant translates the event into a shock, says which size it chose and why, and every
number in its reply comes from a tool call on the twin, not from the model's memory.

## 11:00 The open bet (60 s)

Open **CMG**, then the sealed-forecasts tab.
> "Chipotle's Q3 forecast was sealed on Sunday, October 18, and anchored in Bitcoin. It resolves on October 28, a week after
> today. Delta's resolved on October 9: the margin was a hit, revenue missed, and the miss is published with the
> reason."

Back to the deck, slide 14.

## If something breaks

- **Blank page:** the API isn't running. Restart `uvicorn api.serve:app --port 8000`.
- **Live onboarding fails** (SEC slow, Anthropic error): say so plainly, show `specs/auto/ccl.onboarding.json`
  instead. A GDELT 429 in the output is expected and harmless; the run carries on.
- **A twin errors:** switch to DAL or UAL, the most robust.
- **Chat unavailable:** skip to 11:00 and use the time for questions.
- **Everything fails:** play the backup video.

## Hand-over: Longaeva volunteers try it themselves

The finals include "real-world testing with Longaeva investment team volunteers". Hand them the laptop on the
**Portfolio** page, with the dashboard running and a second terminal open in the repo root. Offer these four
things, about 2 minutes each, and let them drive:

1. **Open any twin and run a scenario.** Click a preset (*Food-safety scare*, *Fuel / commodity spike*, *Demand
   slump*…) or drag a state slider. The forecast band and the *Scenario impact* bars move. Click a driver bar to see
   the data series behind it.
2. **Economy shock.** On Portfolio, click *Jet fuel +30%* or *Restaurant sales −5%*: every exposed twin responds.
3. **Ask the twin.** Chat panel, any question in plain words ("What happens to Delta's margin if fares fall 10%?").
   Every number in the answer comes from a tool call on the twin.
4. **Build a company of their choice.** `python scripts/make_twin.py <TICKER>` (about 1–2 minutes; a GDELT 429
   line is normal). Then refresh and open `#/twin/<TICKER>`.

**Tickers that build** (SEC industry code checked 2026-10-19): restaurants YUM, WING; airlines JBLU, ALK; hotels H,
WH; homebuilders TOL, NVR; general retail DG, DLTR, COST, M. Avoid recent IPOs such as CAVA (2023): too few quarters
to score. Add `--llm` only for a company no pack covers that is still driven by operations (cruise lines: RCL); it
costs about $0.20–0.40 per run, so keep it to one or two.

**When they pick something outside the system** (a bank, a biotech, a chip maker), let it refuse. It prints one
line, for example `[JPM] NOT COVERED: no industry pack covers SIC 6021 …`. With `--llm`, the model reads the 10-K
and agrees: on 2026-10-19 for JPMorgan it answered that none of the packs fit a diversified bank, quoting the
10-K. Say: "It is built for businesses driven by observable operations. It refuses rather than inventing a model.
Banks need their own template (deposits, credit quality, funding cost), and that is first on the roadmap after
deeper twins."

**Don't:** close the dashboard terminal; run `--llm` on many tickers; promise a new twin's accuracy before its
scores print (read the skill numbers off the screen, negatives included).
