# Manual validation sample

Open each source, find the number, and write y (matches) or n (does not) in the last column. Then run `python scripts/validate_ground_truth.py --apply`.

Rows marked (XBRL) link the 10-Q or 10-K. Find the income statement: revenue growth is this quarter's total revenue over the same quarter a year earlier, minus 1, in percent; operating margin is operating income over total revenue. A Q4 value is the full year minus the first nine months, so check it against the 10-K. Small rounding differences (under 0.1) count as a match.

| Twin | Period | KPI | Value | Source | Matches (y/n) |
|---|---|---|---|---|---|
| CMG | 2016Q1 | rlom | 6.80 | https://www.sec.gov/Archives/edgar/data/1058090/000105809016000067/cmg-20160426xex99.htm | |
| CMG | 2019Q3 | revenue_growth | 14.59 | https://www.sec.gov/Archives/edgar/data/1058090/000105809019000038/ (XBRL) | |
| CMG | 2023Q4 | comps | 8.40 | https://www.sec.gov/Archives/edgar/data/1058090/000105809024000006/cmg-20240206xex99_1.htm | |
| DHI | 2018Q1 | revenue_growth | 16.71 | https://www.sec.gov/Archives/edgar/data/882184/000088218418000075/ (XBRL) | |
| DRI | 2021Q2 | op_margin | 14.19 | https://www.sec.gov/Archives/edgar/data/940944/000094094421000041/ (XBRL) | |
| DRI | 2024Q1 | revenue_growth | 6.77 | https://www.sec.gov/Archives/edgar/data/940944/000094094424000017/ (XBRL) | |
| LEN | 2011Q1 | revenue_growth | -2.85 | https://www.sec.gov/Archives/edgar/data/920760/000119312511093934/ (XBRL) | |
| MAR | 2016Q1 | revenue_growth | 7.37 | https://www.sec.gov/Archives/edgar/data/1048286/000162828016014893/ (XBRL) | |
| MCD | 2012Q3 | op_margin | 31.98 | https://www.sec.gov/Archives/edgar/data/63908/000006390812000044/ (XBRL) | |
| MCD | 2014Q3 | revenue_growth | -4.59 | https://www.sec.gov/Archives/edgar/data/63908/000006390814000077/ (XBRL) | |
| MCD | 2026Q1 | revenue_growth | 9.42 | https://www.sec.gov/Archives/edgar/data/63908/000006390826000051/ (XBRL) | |
| PHM | 2016Q2 | revenue_growth | 40.59 | https://www.sec.gov/Archives/edgar/data/822416/000082241616000085/ (XBRL) | |
| TGT | 2009Q3 | revenue_growth | -2.62 | https://www.sec.gov/Archives/edgar/data/27419/000110465909052321/ (XBRL) | |
| TGT | 2021Q1 | revenue_growth | 21.11 | https://www.sec.gov/Archives/edgar/data/27419/000002741921000010/ (XBRL) | |
| TXRH | 2022Q3 | op_margin | 7.58 | https://www.sec.gov/Archives/edgar/data/1289460/000155837022016348/ (XBRL) | |
| TXRH | 2023Q1 | op_margin | 8.60 | https://www.sec.gov/Archives/edgar/data/1289460/000155837023008209/ (XBRL) | |
| TXRH | 2023Q1 | revenue_growth | 18.92 | https://www.sec.gov/Archives/edgar/data/1289460/000155837023008209/ (XBRL) | |
| TXRH | 2025Q2 | revenue_growth | 7.94 | https://www.sec.gov/Archives/edgar/data/1289460/000155837025007082/ (XBRL) | |
| TXRH | 2026Q2 | op_margin | 8.50 | https://www.sec.gov/Archives/edgar/data/1289460/000110465926092408/ (XBRL) | |
| UAL | 2019Q2 | revenue_growth | 5.80 | https://www.sec.gov/Archives/edgar/data/100517/000010051719000021/ (XBRL) | |
