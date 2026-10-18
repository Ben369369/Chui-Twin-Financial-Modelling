You are drafting the company-specific parts of an operating-model spec ("twin") for a public company,
from its latest annual report (10-K). A twin treats public data series as noisy sensors of hidden
operating states, links those states to quarterly KPIs through a causal graph, and forecasts the KPIs.
Code will check everything you return; anything that fails a check is dropped, so precision beats
coverage.

## Company
{{company}}

## Hidden states (template "{{template}}")
{{primitives}}

## Industry packs (shared data series per industry)
{{packs}}

## Data series that can be used as drivers
Already fetched by the system:
{{series_catalog}}
You may also propose a FRED series id as `fred:<ID>` when you are confident it exists, it is monthly or
more frequent, has history since at least 2014, and it measures something the 10-K names as a driver
(for example a commodity the company buys). Code fetches it and drops it if it does not exist.

## KPIs the twin already forecasts
{{default_kpis}}

## XBRL concepts this company reports quarterly (name: label)
{{xbrl_concepts}}

## Your task
Read the 10-K below and return:

1. `pack`: the industry pack whose shared series fit this business best, with the reason. Use "none" if
   no pack fits.
2. `drivers`: at most 4 data series, not already in the chosen pack, that the 10-K names or clearly
   implies as a driver of demand, price, input cost, labor or capacity (for example "fuel is our
   largest expense", "beef prices", "consumer travel demand"). Give the hidden state it measures, the
   sign (+1 if a rise in the series means a rise in that state), a lag in days (0 unless the 10-K
   describes hedging or contracts that delay the effect), the transform (`yoy_log` for prices,
   volumes and indexes; `yoy_diff` for rates already in percent), and strength (`moderate` if the
   10-K quantifies the exposure, else `weak`).
3. `kpis`: at most 2 extra quarterly KPIs that matter for this business and can be computed from the
   XBRL concepts listed above. `yoy` is the year-over-year growth of one concept (list fallbacks in
   priority order). `ratio` is a concept as a percent of total revenue (for example fuel expense as a
   percent of revenue). Use only concept names from the list. Name the KPI in snake_case.
4. `edges`: how strongly each hidden state moves each KPI (default KPIs and your new ones), in
   standardized units between -1 and 1 (a one-sd move in the state moves the KPI by that many sd).
   Only give edges you can support from the 10-K; the defaults stay for the rest.
5. `operating_kpis`: up to 4 operating metrics the company reports outside XBRL that an analyst would
   track (comparable sales, RevPAR, load factor, deliveries, net berth days). These are recorded as
   suggestions only.

Every item needs `quote`: a sentence or clause copied exactly from the 10-K (8 to 60 words) that
supports it. Copy it character for character; do not paraphrase, join separate passages or add
ellipses. Code checks each quote against the filing and drops items whose quote is not found.
Base every choice on the 10-K. Do not use what you know about how the company's KPIs turned out.

## 10-K ({{filing}})
{{text}}
