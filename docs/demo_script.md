# Demo script (5 minutes)

**Before the call:** run `uvicorn api.serve:app --port 8000` and open http://localhost:8000. Click once through
Portfolio and CMG so everything is warm. Keep `docs/sealed_forecasts.md` open in a second tab.

## 0:00 Open on the system, not on Chipotle (45 s)

**Portfolio view.**
> "This is Chui Twin. It turns any public company into a runnable operating model from public data. There are 16
> twins across 5 industries, and 14 of them were built from nothing but the ticker."

Point at the four tiles, then the dot chart.
> "Every twin is scored the same way: walk-forward from 2017, refit at each earnings release using only data that
> was public at that moment. Dots right of zero beat a 'same as last quarter' forecast. Airlines are strong.
> Restaurants straddle zero, and I'll show you why."

## 0:45 How a new company gets in (45 s)

Explain while scrolling the table:
> "The factory looks the ticker up at the SEC, reads its industry code, attaches that industry's shared public
> signals, verifies the company's Wikipedia page by finding the ticker in its infobox, and pulls the KPIs from XBRL,
> which every filer publishes the same way. A new industry is one config file. The engine has no company code, and
> a test enforces that."

## 1:30 One shock, many companies (60 s)

**Economy shock card.** Click **Jet fuel +30%**.
> "Move one shared series and every exposed twin responds through its own calibrated model. Jet fuel up 30% cuts
> next-quarter operating margin by 1.5 to 1.9 points across Delta, United, American and Southwest, while revenue
> edges up through fare pass-through."

Click **Restaurant sales −5%**.
> "Same mechanism, a different part of the economy."

## 2:30 Inside one twin (75 s)

Click a Delta bar to open **DAL**.
> "Here's revenue growth, with an 80% band. The grey diamond is Delta's own guidance, mid-teens, which the system
> read out of the press release. The twin starts from guidance and forecasts the surprise. It adds about a point
> for Delta's habit of beating guidance and takes some off for softening airfares. Each bar here is one data
> series, and clicking it shows the exact source."

Click a driver bar, show the sources, then the **Fuel / commodity spike** preset.

## 3:45 Honesty and the live test (60 s)

Open **CMG**:
> "On Chipotle, analyst consensus still beats the twin: a mean error of 1 point against 2.5. Free public data
> carries little Chipotle-specific information, and I'd rather show that than hide it. Against Delta's own
> guidance, the twin wins."

Switch to the sealed-forecasts tab:
> "This is a live test. The Delta Q3 forecast, median 15.2% and 80% range 10.6 to 19.9, was sealed and timestamped
> in the Bitcoin blockchain before Delta reports around October 9. Chipotle's gets sealed the day before October 28."

## 4:45 Ask (15 s)

> "Two questions for you: is a cross-industry scorecard plus live sealed forecasts the right proof of
> scalability? And should I prioritize beating consensus on one company, or matching it across many?"

## If something breaks

- **Blank page:** the API isn't running. Restart `uvicorn api.serve:app`.
- **A twin errors:** switch to DAL or UAL, the most robust.
- **Questions about the model:** the math is in `docs/model.md`, the data sources in `provenance.md`.
