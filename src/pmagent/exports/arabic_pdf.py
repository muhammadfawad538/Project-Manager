# Line ending: LF
# Encoding: UTF-8

"""
Arabic PDF export for pmagent.

Generates RTL Arabic PDFs from markdown content using WeasyPrint.
Falls back to basic HTML generation if WeasyPrint is not installed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Try to import WeasyPrint; fall back gracefully if not installed
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

from pmagent.utils import format_currency, format_vat, get_country_config


# Arabic-safe font stack for PDF generation
# These fonts are bundled with most Linux/Windows systems or available via Google Fonts
ARABIC_FONTS_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Amiri:ital,wght@0,400;0,700;1,400&family=Noto+Naskh+Arabic:wght@400;700&family=Cairo:wght@400;600;700&display=swap');

@page {
    size: A4;
    margin: 2.5cm;
    direction: rtl;
    text-align: right;
}

body {
    font-family: 'Amiri', 'Noto Naskh Arabic', 'Cairo', 'Arial', sans-serif;
    font-size: 11pt;
    line-height: 1.8;
    direction: rtl;
    text-align: right;
}

h1 {
    font-family: 'Cairo', 'Amiri', sans-serif;
    font-size: 18pt;
    font-weight: 700;
    color: #1a1a1a;
    border-bottom: 2px solid #c9a84c;
    padding-bottom: 8px;
    margin-top: 24pt;
}

h2 {
    font-family: 'Cairo', 'Amiri', sans-serif;
    font-size: 14pt;
    font-weight: 600;
    color: #2c5f7c;
    margin-top: 18pt;
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 4px;
}

h3 {
    font-family: 'Cairo', 'Amiri', sans-serif;
    font-size: 12pt;
    font-weight: 600;
    color: #444;
    margin-top: 12pt;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 12pt 0;
    font-size: 9pt;
    direction: rtl;
    text-align: right;
}

thead th {
    background-color: #1e4d6b;
    color: white;
    padding: 8px 6px;
    font-weight: 600;
    border: 1px solid #1e4d6b;
    font-family: 'Cairo', sans-serif;
    font-size: 9pt;
}

tbody td {
    padding: 6px;
    border: 1px solid #d0d0d0;
    text-align: right;
    vertical-align: top;
}

tbody tr:nth-child(even) {
    background-color: #f8f9fa;
}

ul, ol {
    padding-right: 20px;
    padding-left: 0;
}

li {
    margin-bottom: 4px;
}

.cover-page {
    page-break-after: always;
    text-align: center;
    padding-top: 120px;
}

.cover-page h1 {
    font-size: 24pt;
    border: none;
    color: #1e4d6b;
}

.cover-page .project-name {
    font-size: 20pt;
    font-weight: 700;
    color: #1a1a1a;
    margin: 40px 0;
}

.cover-page .meta-info {
    font-size: 12pt;
    color: #555;
    line-height: 2.5;
}

.page-footer {
    font-size: 8pt;
    color: #888;
    text-align: center;
    border-top: 1px solid #ddd;
    padding-top: 6px;
    margin-top: 30px;
}

.signature-section {
    page-break-before: always;
    margin-top: 60px;
}

.signature-table td {
    height: 80px;
    vertical-align: bottom;
}
"""


def markdown_to_html_rtl(markdown_content: str, project_name: str = "") -> str:
    """Convert markdown content to RTL HTML suitable for Arabic PDF generation.

    Args:
        markdown_content: Markdown string (already in Arabic)
        project_name: Project name for the cover page

    Returns:
        HTML string with RTL layout and Arabic fonts
    """
    # Basic markdown to HTML conversion (no external deps)
    import re

    html = markdown_content

    # Escape HTML special chars first (but preserve our markdown syntax)
    html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Headers
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    # Tables (basic markdown table support)
    lines = html.split("\n")
    in_table = False
    result = []
    table_rows = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped[1:-1].split("|")]
            # Skip separator rows (|---|---|)
            if all("-" in c for c in cells):
                continue
            table_rows.append(cells)
            in_table = True
        else:
            if in_table and table_rows:
                result.append(_render_table(table_rows))
                table_rows = []
                in_table = False
            result.append(line)

    if in_table and table_rows:
        result.append(_render_table(table_rows))

    html = "\n".join(result)

    # Lists
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"(<li>.*</li>\n?)+", lambda m: f"<ul>\n{m.group(0)}</ul>\n", html)

    # Paragraphs (double newline)
    html = re.sub(r"\n\n+", r"</p><p>", html)
    html = f"<p>{html}</p>"

    # Clean up empty paragraphs
    html = re.sub(r"<p>\s*</p>", "", html)
    html = re.sub(r"<p>(<h[123]>|<ul>|<table>)", r"\1", html)
    html = re.sub(r"(</h[123]>|</ul>|</table>)</p>", r"\1", html)

    # Wrap with cover page and styles
    cover = f"""
    <div class="cover-page">
        <h1>حزمة إدارة المشروع</h1>
        <div class="project-name">{project_name}</div>
        <div class="meta-info">
            <div>تم إعداد هذا المستند بواسطة pmagent</div>
            <div>نظام إدارة المشاريع بالذكاء الاصطناعي</div>
        </div>
    </div>
    """

    full_html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <title>{project_name}</title>
    <style>
{ARABIC_FONTS_CSS}
    </style>
</head>
<body>
{cover}
{html}
<div class="page-footer">
    صفحة <span class="page-number"></span> من <span class="total-pages"></span>
</div>
</body>
</html>"""

    return full_html


def _render_table(rows: list[list[str]]) -> str:
    """Render a markdown table as HTML."""
    if not rows:
        return ""

    header = rows[0]
    data = rows[1:]

    # Build table HTML
    parts = ['<table>', '  <thead>', '    <tr>']
    for cell in header:
        parts.append(f"      <th>{cell}</th>")
    parts.extend(['    </tr>', '  </thead>', '  <tbody>'])

    for row in data:
        parts.append('    <tr>')
        for cell in row:
            parts.append(f"      <td>{cell}</td>")
        parts.append('    </tr>')

    parts.extend(['  </tbody>', '</table>'])
    return "\n".join(parts)


def export_arabic_pdf(
    markdown_content: str,
    output_path: str,
    project_name: str = "المشروع",
) -> Optional[str]:
    """Generate an Arabic PDF from markdown content.

    Args:
        markdown_content: Markdown string in Arabic
        output_path: Path to save the PDF
        project_name: Project name for the cover page

    Returns:
        Path to the generated PDF, or None if WeasyPrint is not installed
    """
    if not WEASYPRINT_AVAILABLE:
        print("WeasyPrint not installed. Install with: pip install weasyprint")
        print("Falling back: saving HTML instead.")
        html = markdown_to_html_rtl(markdown_content, project_name)
        html_path = output_path.replace(".pdf", ".html")
        Path(html_path).write_text(html, encoding="utf-8")
        return html_path

    html = markdown_to_html_rtl(markdown_content, project_name)

    try:
        HTML(string=html).write_pdf(
            output_path,
            stylesheets=[CSS(string=ARABIC_FONTS_CSS)],
        )
        return output_path
    except Exception as exc:
        print(f"PDF generation failed: {exc}")
        # Fallback: save HTML
        html_path = output_path.replace(".pdf", ".html")
        Path(html_path).write_text(html, encoding="utf-8")
        return html_path
