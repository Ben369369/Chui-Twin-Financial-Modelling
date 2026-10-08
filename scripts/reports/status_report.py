"""Status report on the Chui Trading letterhead (logo block, Princeton NJ, navy rule, contact footer).

    python scripts/reports/status_report.py        # writes docs/Chui_Twin_status_report_<date>.pdf

Figures are typed in deliberately, each checked against the scorecard, backtests and API on the
report date; regenerate after re-checking them.
"""

from __future__ import annotations

import os
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[2]
DATE = "October 2, 2026"
OUT = ROOT / "docs" / "Chui_Twin_status_report_2026-10-02.pdf"
# Letterhead contact details come from the environment so they never land in the repo.
EMAIL, PHONE = os.environ.get("CHUI_CONTACT_EMAIL", ""), os.environ.get("CHUI_CONTACT_PHONE", "")

NAVY = colors.HexColor("#1B2A5A")
GREY = colors.HexColor("#5A6270")
RULE = colors.HexColor("#C9D2DC")
LIGHT = colors.HexColor("#EEF1F8")
INK = colors.HexColor("#1E2329")

title = ParagraphStyle("t", fontName="Times-Bold", fontSize=20, leading=24, textColor=NAVY, alignment=TA_CENTER)
sub = ParagraphStyle("s", fontName="Times-Roman", fontSize=11, leading=14, textColor=GREY, alignment=TA_CENTER)
h1 = ParagraphStyle("h1", fontName="Times-Bold", fontSize=13.5, leading=17, textColor=NAVY, spaceBefore=12, spaceAfter=4)
body = ParagraphStyle("b", fontName="Times-Roman", fontSize=11, leading=14.5, textColor=INK, spaceAfter=5)
bullet = ParagraphStyle("bl", parent=body, leftIndent=13, bulletIndent=2, spaceAfter=3)
small = ParagraphStyle("sm", parent=body, fontSize=9, leading=11.5, textColor=GREY)
cell = ParagraphStyle("c", parent=body, fontSize=9.6, leading=12, spaceAfter=0)
cellb = ParagraphStyle("cb", parent=cell, fontName="Times-Bold", textColor=NAVY)


def B(text: str) -> Paragraph:
    return Paragraph(text, bullet, bulletText="•")


def table(data, widths, bold_last=False):
    rows = [[Paragraph(str(c), cellb if r == 0 else cell) for c in row] for r, row in enumerate(data)]
    t = Table(rows, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if bold_last:
        style.append(("FONTNAME", (0, -1), (-1, -1), "Times-Bold"))
    t.setStyle(TableStyle(style))
    return t


def pipeline() -> Drawing:
    w, h = 7.0 * inch, 1.15 * inch
    d = Drawing(w, h)
    steps = [("Observe", "public data, saved raw"), ("Infer", "hidden operating states"),
             ("Simulate", "causal Monte Carlo"), ("Explain", "every number sourced"),
             ("Score", "vs expert baselines")]
    gap = 0.16 * inch
    bw = (w - gap * (len(steps) - 1)) / len(steps)
    bh = 0.8 * inch
    y = (h - bh) / 2
    for i, (name, line) in enumerate(steps):
        x = i * (bw + gap)
        d.add(Rect(x, y, bw, bh, fillColor=NAVY, strokeColor=None))
        d.add(String(x + bw / 2, y + bh - 24, name, fontName="Times-Bold", fontSize=12.5, fillColor=colors.white,
                     textAnchor="middle"))
        d.add(String(x + bw / 2, y + bh - 42, line, fontName="Times-Roman", fontSize=7.8, fillColor=colors.white,
                     textAnchor="middle"))
        if i < len(steps) - 1:
            ax, ay = x + bw + 2, y + bh / 2
            d.add(Line(ax, ay, ax + gap - 7, ay, strokeColor=GREY, strokeWidth=1.3))
            d.add(Polygon([ax + gap - 7, ay + 3.5, ax + gap - 2, ay, ax + gap - 7, ay - 3.5], fillColor=GREY, strokeColor=None))
    return d


def letterhead(canvas, doc):
    """Logo block centered, Princeton NJ, navy rule; footer with email, page, phone (as on the letterhead)."""
    canvas.saveState()
    pw, ph = letter
    size = 0.95 * inch
    x0, y0 = (pw - size) / 2, ph - 0.45 * inch - size
    canvas.setFillColor(NAVY)
    canvas.rect(x0, y0, size, size, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 19)
    canvas.drawRightString(x0 + size - 7, y0 + 30, "Chui")
    canvas.setFont("Helvetica", 12.5)
    canvas.drawRightString(x0 + size - 7, y0 + 14, "Trading")
    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Oblique", 8.5)
    canvas.drawCentredString(pw / 2, y0 - 13, "Princeton, NJ")
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(0.8)
    canvas.line(0.75 * inch, y0 - 18, pw - 0.75 * inch, y0 - 18)
    canvas.setStrokeColor(RULE)
    canvas.line(0.75 * inch, 0.62 * inch, pw - 0.75 * inch, 0.62 * inch)
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(NAVY)
    canvas.drawString(0.85 * inch, 0.46 * inch, EMAIL)
    canvas.drawRightString(pw - 0.85 * inch, 0.46 * inch, PHONE)
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(pw / 2, 0.36 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build() -> Path:
    s = []
    s.append(Paragraph("Chui Twin: Status Report", title))
    s.append(Paragraph(f"Longaeva AI Hackathon, Stage 2 | For Doug Rogers<br/>"
                       f"Benedict Kiprotich Ngetich | Chui Trading, a Chui Labs company | {DATE}", sub))
    s.append(Spacer(1, 6))

    s.append(Paragraph("Summary", h1))
    s.append(B("<b>Chui Twin is a system, not a model of one company.</b> One engine turns a public company into a "
               "runnable operating model. <b>16 twins are live across 5 industries</b>; 14 were built by a factory from "
               "the ticker alone, with no hand-written configuration and no per-company tuning."))
    s.append(B("<b>Every twin is scored the same way</b>, walk-forward from 2017 using only data public at each "
               "earnings release. The twin beats a “same as last quarter” forecast on <b>21 of 33</b> KPI series "
               "and a “same quarter last year” forecast on <b>31 of 33</b>."))
    s.append(B("<b>All three bars you suggested are now in.</b> The twin beats Delta's own revenue guidance. "
               "On Chipotle it does not yet beat analyst consensus, and the report says so."))
    s.append(B("<b>A live test is sealed.</b> A forecast of Delta's Q3 2026 revenue growth is timestamped in the "
               "Bitcoin blockchain via OpenTimestamps, before Delta reports (around October 9)."))

    s.append(Paragraph("How it works", h1))
    s.append(pipeline())
    s.append(Paragraph(
        "Public data is treated as noisy sensors of a company's hidden operating states: demand, capacity, price, "
        "input cost, labor and sentiment. The engine estimates those states each quarter and links them to reported "
        "KPIs through a causal graph with stated priors. It then simulates thousands of paths forward, returning a "
        "distribution, a driver breakdown down to each data series, and scenarios. Where management guidance or "
        "analyst consensus exists, the twin forecasts the <i>surprise</i> relative to it: the expectation gap from "
        "the Stage 1 proposal.", body))

    s.append(Paragraph("Why it scales", h1))
    s.append(table([
        ["Layer", "Shared by every twin", "A new company or industry needs"],
        ["Engine", "Estimation, simulation, attribution, scoring. A test fails if any company or industry name "
                   "appears in engine code.", "Nothing"],
        ["Data adapters", "SEC EDGAR and XBRL, FRED, BLS, TSA, Wikipedia views, GDELT news tone, public sitemaps "
                          "with Internet Archive history. One TSA adapter serves every airline and hotel.", "Usually nothing"],
        ["Industry packs", "One short file per industry: which public series inform which states. Five exist.",
         "One file per industry"],
        ["Twin factory", "Ticker → SEC record → industry pack → scored twin. The company's Wikipedia page "
                         "is accepted only if its infobox lists the ticker.", "Just the ticker"],
    ], [1.15 * inch, 3.85 * inch, 2.0 * inch]))

    s.append(KeepTogether([Paragraph("Evidence", h1), table([
        ["Bar", "Result", "Notes"],
        ["Last quarter (naive)", "Beats it on 21 of 33 KPI series", "Strongest in airlines: 8 of 8"],
        ["Same quarter last year", "Beats it on 31 of 33", ""],
        ["Management guidance", "Delta revenue growth: CRPS 28% better than guidance (13 guided quarters)",
         "Guidance extracted automatically from releases, each value with its source sentence"],
        ["Analyst consensus", "Chipotle comps: <b>consensus still wins</b>, mean error 1.0 vs 2.5 points (6 quarters)",
         "Consensus taken from published news coverage, each figure with URL and quote"],
    ], [1.45 * inch, 3.1 * inch, 2.45 * inch])]))
    s.append(Paragraph("Full per-company results are in the dashboard and in docs/portfolio_scorecard.md. CRPS is a "
                       "standard score for probabilistic forecasts that rewards accuracy and honest uncertainty.", small))

    s.append(Paragraph("New since my last note", h1))
    s.append(B("<b>Dashboard.</b> A portfolio scorecard, a twin view (forecast band, guidance marker, drivers you can "
               "click through to their sources, hidden states) and scenarios. Every chart has a table view."))
    s.append(B("<b>Economy shock.</b> Move one shared data series and every exposed twin responds through its own "
               "model. Example: jet fuel +30% year over year cuts next-quarter operating margin by 1.5 to 1.9 points "
               "across Delta, United, American and Southwest."))
    s.append(B("<b>Company scenario.</b> A food-safety-scale sentiment shock (−2.5 sd) cuts Chipotle's next-quarter "
               "transactions by about 6.5 points and revenue growth by 8. (This replaces the “comps −10” "
               "figure in my last note, which came from an earlier model.)"))
    s.append(B("<b>Data quality caught by the system.</b> Physical bounds (a margin cannot exceed 100%) exposed "
               "McDonald's margins being computed on company-operated sales only. Fixing it cut that twin's error from "
               "8.9 to 3.5 points."))

    s.append(KeepTogether([
        Paragraph("Known limits", h1),
        B("<b>Free public data carries little Chipotle-specific information</b> about next quarter's comps, which is "
          "why consensus wins there. The edge so far is in airlines and in operating margins."),
        B("<b>Related KPIs are fitted separately</b>, so they can respond inconsistently to the same shock (Chipotle "
          "comps move less than transactions). Enforcing accounting identities across simulated paths is next."),
        B("<b>Some macro series are stored in their latest revised form</b>, which slightly flatters history. "
          "Model structures were partly chosen on the reported backtest; the sealed forecasts and the untuned "
          "factory twins are the clean tests."),
    ]))

    s.append(KeepTogether([Paragraph("Next steps", h1), table([
        ["When", "Milestone"],
        ["By Oct 9", "Accounting-identity constraints across KPIs. Delta's sealed forecast resolves. Stage 2 package: "
                     "dashboard, scorecard, coverage document."],
        ["By Oct 21", "LLM onboarding: a model reads the 10-K to choose company-specific KPIs and draft extraction "
                      "rules, every value keeping its source text. Turning news into scenario shocks. A shock library "
                      "with decay shapes measured from real events (2015 E. coli, 2024 CrowdStrike outage, COVID)."],
        ["Oct 27–28", "Chipotle Q3 forecast sealed the day before results, then scored."],
    ], [1.0 * inch, 6.0 * inch])]))

    s.append(Paragraph("Ask", h1))
    s.append(Paragraph(
        "A 30-minute Zoom on October 5 or 6 for a live demo. Two questions: (1) is a cross-industry scorecard plus "
        "live sealed forecasts the right proof of scalability for the judges; and (2) would you weigh beating "
        "consensus on one company or matching it across many?", body))

    doc = SimpleDocTemplate(str(OUT), pagesize=letter, leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                            topMargin=1.85 * inch, bottomMargin=0.85 * inch, title="Chui Twin: Status Report",
                            author="Benedict Kiprotich Ngetich", subject=f"Longaeva AI Hackathon status, {DATE}")
    doc.build(s, onFirstPage=letterhead, onLaterPages=letterhead)
    return OUT


if __name__ == "__main__":
    print(build())
