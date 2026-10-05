# Midpoint check-in brief (Doug Rogers, Oct 5–6)

One page for the call. The 5-minute walkthrough is in `docs/demo_script.md`.

## Before the call (10 minutes)

1. Start the server: `uvicorn api.serve:app --port 8000`, then open http://localhost:8000.
2. Click once through Portfolio, DAL and CMG so everything is loaded.
3. Ask Chui one question ("What happens to airlines if jet fuel rises 30%?") to confirm the assistant is live.
4. Keep `docs/sealed_forecasts.md` open in a second tab.

## What the midpoint asked for, and where it stands

| Midpoint goal | Status |
|---|---|
| Fitted CMG states | Done. Seven states estimated each quarter from 9 public signals; shown on the CMG page. |
| First backtest | Done, and beyond the plan: walk-forward on 16 twins, 33 KPI series, scored against "last quarter", "last year", guidance and consensus. |
| Engine company-agnostic | Done. A test greps the engine for tickers and industry names; a dummy template with made-up states runs end to end. |
| DAL twin | Done and ahead of plan. It beats Delta's own guidance on revenue growth. |

## Three numbers to say

- **16 twins, 5 industries, 14 built from the ticker alone** by the twin factory with no per-company tuning.
- **Beats "same quarter last year" on 31 of 33 KPI series, and "last quarter" on 22 of 33.**
- **One live, sealed out-of-sample forecast:** Delta Q3 revenue growth, median 15.2% (80% range 10.6 to 19.9), timestamped in Bitcoin block 969637 on Oct 2. It resolves when Delta reports (~Oct 9); `scripts/resolve_sealed.py` scores it.

## Say the weak points before he finds them

- Analyst consensus still beats the twin on Chipotle comps (6 quarters with consensus). Free public data carries little Chipotle-specific information.
- Restaurant and hotel revenue growth roughly ties "last quarter" (skill near zero); airlines are where the signals are strongest.
- Scenarios are what a calibrated linear model implies. Moves far outside history (a 30% fare increase) are extrapolation, and the tool says so.

## Questions to ask Doug

1. Is a cross-industry scorecard plus live sealed forecasts the proof of scalability the judges want?
2. Depth or breadth for the next two weeks: beat consensus on one company, or match it across many?
3. Does Longaeva have consensus estimates or other licensed data we may use? Right now consensus is hand-entered from public news quotes.
4. For finals, which matters more: LLM onboarding (a 10-K becomes a spec), a third industry template (banks), or the live demo?

## Plan to Oct 9 (Stage 2)

- Oct 6–8: finish the Stage 2 package: refresh the coverage doc and status report, record a demo video as a backup.
- ~Oct 9: Delta reports. Run `python scripts/run_daily.py`, then `python scripts/resolve_sealed.py`, and share the result whichever way it goes.
- After Oct 9: LLM onboarding, the bank template, and sealing the Chipotle forecast on Oct 27.
