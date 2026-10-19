"""
Renders a markdown file to PDF with the theme in tokens.json, using pandoc's
Typst writer and the Typst compiler. No LibreOffice or LaTeX needed.

Usage:
    python3 render_pdf_typst.py <input.md> <output.pdf> [--tokens tokens.json]

Requires pandoc >= 3.1.2 and either the `typst` Python package
(`pip install typst`) or a `typst` binary on PATH.

Sizes and spacing mirror build_reference_docx.py. The output matches the .docx
theme in colors, fonts, margins and heading structure; line breaks can differ.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Fonts tried after the token font. Typst skips families that are not installed.
SANS_FALLBACK = ["Carlito", "Helvetica Neue", "Arial", "Liberation Sans", "DejaVu Sans"]
MONO_FALLBACK = ["Menlo", "Courier New", "Liberation Mono", "DejaVu Sans Mono"]


def find_pandoc():
    """$PANDOC, then PATH, then a static binary at assets/bin/pandoc."""
    for candidate in (os.environ.get("PANDOC"), shutil.which("pandoc"), str(HERE / "bin" / "pandoc")):
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    sys.exit("pandoc not found. Install it with your package manager, or download a static binary from "
             "https://github.com/jgm/pandoc/releases and set PANDOC=/path/to/pandoc "
             f"(or place it at {HERE / 'bin' / 'pandoc'}).")


def mix(color, other, ratio):
    """Blend '#RRGGBB' color toward other by ratio, 0..1; same as build_reference_docx.py."""
    a = [int(color.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(other.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    return '#' + ''.join(f"{round(x + (y - x) * ratio):02X}" for x, y in zip(a, b))


def font_list(primary, fallback):
    return "(" + ", ".join(f'"{f}"' for f in [primary, *fallback]) + ")"


def style_rules(t):
    c, f = t["colors"], t["fonts"]
    ink, accent, muted = c["ink"], c["accent"], c["muted"]
    tint = c.get("tint") or accent
    rule = c.get("rule") or ink
    band = c.get("band") or mix(ink, "#FFFFFF", 0.93)
    heading = font_list(f.get("heading", f["body"]), SANS_FALLBACK)
    mono = font_list(f.get("mono", "Consolas"), MONO_FALLBACK)
    return f'''
#set text(fill: rgb("{ink}"))
#set par(leading: 0.78em, spacing: 1.05em, justify: false)
#set list(spacing: 0.55em)
#set enum(spacing: 0.55em)

#show heading.where(level: 1): it => block(width: 100%, above: 0pt, below: 18pt, {{
  align(center, text(font: {heading}, size: 26pt, weight: "bold", fill: rgb("{ink}"), it.body))
  v(-2pt)
  line(length: 100%, stroke: 0.75pt + rgb("{accent}"))
}})
#show heading.where(level: 2): it => block(above: 22pt, below: 8pt,
  text(size: 15pt, weight: "bold", fill: rgb("{accent}"), it.body))
#show heading.where(level: 3): it => block(above: 14pt, below: 4pt,
  text(size: 12pt, weight: "bold", fill: rgb("{muted}"), it.body))
#show heading.where(level: 4): it => block(above: 12pt, below: 3pt,
  text(size: 11.5pt, weight: "bold", fill: rgb("{ink}"), it.body))
#show heading.where(level: 5): it => block(above: 10pt, below: 2pt,
  text(size: 11pt, weight: "bold", fill: rgb("{muted}"), it.body))

#show raw: set text(font: {mono}, fill: rgb("{ink}"))
#show raw.where(block: false): set text(size: 9.5pt)
#show raw.where(block: true): it => block(width: 100%, inset: (left: 8pt),
  stroke: (left: 1.5pt + rgb("{rule}")), text(size: 8.5pt, it))

#show quote.where(block: true): it => block(width: 100%, inset: (left: 9pt, y: 2pt),
  above: 6pt, below: 10pt, stroke: (left: 2.25pt + rgb("{accent}")),
  text(size: 10.5pt, style: "italic", fill: rgb("{muted}"), it.body))

#set table(stroke: none, inset: 6pt, fill: (x, y) =>
  if y == 0 {{ rgb("{tint}") }} else if calc.even(y) {{ rgb("{band}") }} else {{ none }})
#show table.cell.where(y: 0): set text(weight: "bold")

#show figure.caption: set text(size: 9pt, style: "italic", fill: rgb("{muted}"))
#show figure: set block(above: 10pt, below: 16pt)
'''


def run_typst(typ, pdf, root):
    try:
        import typst
        typst.compile(str(typ), output=str(pdf), root=str(root))
        return
    except ImportError:
        pass
    binary = shutil.which("typst")
    if not binary:
        sys.exit("Typst not found. Install it with: pip install typst")
    subprocess.run([binary, "compile", "--root", str(root), str(typ), str(pdf)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--tokens", default=str(HERE / "tokens.json"))
    a = ap.parse_args()

    pandoc = find_pandoc()
    t = json.loads(Path(a.tokens).read_text())
    src = Path(a.input).resolve()
    out = Path(a.output).resolve()
    m = {"top": 2.2, "bottom": 2.2, "left": 2.4, "right": 2.4, **t.get("margins_cm", {})}
    body_fonts = [t["fonts"]["body"], *SANS_FALLBACK]

    with tempfile.TemporaryDirectory() as tmp:
        header = Path(tmp) / "header.typ"
        header.write_text(style_rules(t))
        # The .typ must sit inside the Typst root so relative image paths resolve.
        typ = src.parent / f".{src.stem}.render.typ"
        try:
            meta = Path(tmp) / "meta.yaml"
            meta.write_text(
                f'mainfont: "{body_fonts[0]}"\n'
                "fontsize: 11pt\n"
                'page-numbering: ""\n'
                "margin:\n"
                + "".join(f"  {k}: {m[k]}cm\n" for k in ("top", "bottom", "left", "right"))
            )
            cmd = [pandoc, str(src), "--from=markdown+smart", "--to=typst",
                   "--include-in-header", str(header),
                   "--metadata-file", str(meta),
                   "--resource-path", str(src.parent),
                   "-o", str(typ)]
            subprocess.run(cmd, check=True)
            # pandoc accepts one main font; extend it to the fallback list.
            text = typ.read_text()
            text = text.replace(f'font: ("{body_fonts[0]}",)', f"font: {font_list(body_fonts[0], body_fonts[1:])}", 1)
            typ.write_text(text)
            out.parent.mkdir(parents=True, exist_ok=True)
            run_typst(typ, out, src.parent)
        finally:
            typ.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
