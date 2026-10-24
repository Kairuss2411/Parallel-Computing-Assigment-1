#!/usr/bin/env python3
"""Convert the Part 1 Markdown report to a printable HTML file.

Usage: python3 scripts/md_to_html.py report/report_part1.md [out.html]
The HTML keeps relative image paths, so the output must stay in report/.
Open it in a browser and use Print -> Save as PDF.
"""
import os
import sys

import markdown

src = sys.argv[1] if len(sys.argv) > 1 else "report/report_part1.md"
dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + ".html"

with open(src, encoding="utf-8") as f:
    text = f.read()

body = markdown.markdown(
    text,
    extensions=["extra", "tables", "fenced_code", "sane_lists"],
    output_format="html5",
)

CSS = """
:root { --fg:#1f2328; --muted:#57606a; --line:#d0d7de; --accent:#0969da; }
* { box-sizing: border-box; }
body {
  font-family: "Segoe UI", "Noto Sans", "DejaVu Sans", Arial, sans-serif;
  color: var(--fg); line-height: 1.55; max-width: 980px;
  margin: 0 auto; padding: 32px 24px 64px;
}
h1 { font-size: 1.9em; border-bottom: 2px solid var(--line); padding-bottom: .3em; }
h2 { font-size: 1.45em; margin-top: 1.8em; border-bottom: 1px solid var(--line); padding-bottom: .2em; }
h3 { font-size: 1.15em; margin-top: 1.4em; }
p, li { font-size: 15px; }
a { color: var(--accent); }
code { background: #f6f8fa; padding: .15em .35em; border-radius: 4px; font-size: .9em; }
pre { background: #f6f8fa; border: 1px solid var(--line); border-radius: 6px;
      padding: 12px 14px; overflow-x: auto; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 13px; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 13.5px; page-break-inside: avoid; }
th, td { border: 1px solid var(--line); padding: 6px 9px; text-align: left; }
th { background: #f6f8fa; }
tr:nth-child(even) td { background: #fbfcfd; }
blockquote { border-left: 4px solid var(--accent); margin: 1em 0; padding: .2em 1em;
             color: var(--muted); background: #f6f8fa; }
img { max-width: 100%; display: block; margin: 1em auto; page-break-inside: avoid; }
hr { border: none; border-top: 1px solid var(--line); margin: 2em 0; }
@page { size: A4; margin: 16mm 14mm; }
@media print {
  body { max-width: none; padding: 0; }
  a { color: inherit; text-decoration: none; }
  h2, h3 { page-break-after: avoid; }
}
"""

html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Báo cáo Assignment 1 – Phần 1: Mutex Locks</title>
<style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>
"""

with open(dst, "w", encoding="utf-8") as f:
    f.write(html)
print("wrote", dst)
