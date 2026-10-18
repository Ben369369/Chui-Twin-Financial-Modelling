"""Render a markdown document to a branded PDF with headless Chrome or Edge.

    python scripts/reports/appendix_pdf.py      # docs/technical_appendix.md -> docs/Chui_Twin_Technical_Appendix.pdf
    python scripts/reports/appendix_pdf.py docs/project_structure.md docs/Chui_Twin_Project_Structure.pdf
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs" / "technical_appendix.md"
OUT = ROOT / "docs" / "Chui_Twin_Technical_Appendix.pdf"
BROWSERS = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "google-chrome", "chromium", "msedge"]

CSS = """
@page { size: letter; margin: 0.7in 0.75in 0.75in; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10pt; line-height: 1.45; color: #1E2329; }
.mast { display: flex; align-items: center; gap: 12px; border-bottom: 2px solid #1B2A5A; padding-bottom: 8px; margin-bottom: 18px; }
.logo { background: #1B2A5A; color: #fff; width: 46px; height: 46px; display: flex; flex-direction: column;
        align-items: center; justify-content: center; font-family: Georgia, serif; font-weight: 700; font-size: 12pt; line-height: 1; }
.logo small { font-family: Arial, sans-serif; font-weight: 400; font-size: 6.5pt; margin-top: 2px; }
.mast .who { font-size: 8.5pt; color: #5A6270; }
h1 { font-family: Georgia, serif; color: #1B2A5A; font-size: 20pt; margin: 0 0 4px; }
h2 { font-family: Georgia, serif; color: #1B2A5A; font-size: 13pt; margin: 20px 0 6px; border-bottom: 1px solid #C9D2DC; padding-bottom: 3px; break-after: avoid; }
p, li { margin: 4px 0; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 10px; font-size: 8.8pt; break-inside: avoid; }
th { background: #EEF1F8; color: #1B2A5A; text-align: left; }
th, td { border: 1px solid #C9D2DC; padding: 4px 6px; vertical-align: top; }
code { font-family: Consolas, monospace; font-size: 8.6pt; background: #F3F5F9; padding: 0 2px; }
pre { background: #F3F5F9; border: 1px solid #DDE3EC; padding: 8px 10px; font-size: 8pt; line-height: 1.35; overflow: hidden; break-inside: avoid; }
pre code { background: none; padding: 0; }
a { color: #1F5FB0; }
"""


def browser() -> str:
    for b in BROWSERS:
        if Path(b).exists() or shutil.which(b):
            return b
    raise SystemExit("no Chrome or Edge found for printing")


LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s")


def to_python_markdown(text: str) -> str:
    """GitHub-style lists to Python-Markdown: a blank line before a list, nested items at 4 spaces."""
    out: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and LIST_ITEM.match(line):
            indent = len(line) - len(line.lstrip())
            if 0 < indent < 4:
                line = "    " + line.lstrip()
            if out and out[-1].strip() and not LIST_ITEM.match(out[-1]) and not out[-1].startswith(" "):
                out.append("")
        out.append(line)
    return "\n".join(out)


def main() -> None:
    src, out = (ROOT / sys.argv[1], ROOT / sys.argv[2]) if len(sys.argv) == 3 else (SRC, OUT)
    text = src.read_text(encoding="utf-8")
    title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), "Chui Twin")
    body = markdown.markdown(to_python_markdown(text), extensions=["tables", "fenced_code"])
    # Other documents may carry wide code blocks (file trees): a smaller code face keeps ~120 columns on the page.
    css = CSS if src == SRC else CSS + "pre, pre code { font-size: 6.9pt; } table, pre { break-inside: auto; }"
    html = (f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>"
            f"<style>{css}</style></head><body><div class='mast'><div class='logo'>Chui<small>Trading</small></div>"
            f"<div class='who'>Chui Trading · A Chui Labs company · Princeton, NJ</div></div>{body}</body></html>")
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "appendix.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run([browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--user-data-dir={Path(tmp) / 'profile'}", f"--print-to-pdf={out}", page.as_uri()],
                       check=True, capture_output=True, timeout=120)
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
