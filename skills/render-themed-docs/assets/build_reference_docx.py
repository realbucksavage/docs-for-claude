"""
Regenerates assets/reference.docx — the pandoc --reference-doc theme used by the
render-themed-docs skill.

Run this only when the theme needs a tweak (a color, font, or margin change) or
when pandoc's own default reference.docx changes across a pandoc version bump.
Normal use of the skill does NOT need this script — it just uses the already-built
reference.docx that ships alongside it.

Usage:
    python3 build_reference_docx.py [--tokens tokens.json] [--out reference.docx]

Design tokens (colors, fonts, margins) are read from tokens.json next to this
script unless --tokens is given. "tint", "rule" and "band" are optional; when absent
they are derived from "accent" and "ink". Writes reference.docx next to this script
unless --out is given.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import docx
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn

HERE = Path(__file__).resolve().parent
BASE_DOCX = HERE / "_refbase.docx"

# Design tokens — see references/theme-spec.md for the full rationale.
# Populated by load_tokens() from tokens.json.
INK = ACCENT = MUTED = None   # RGBColor
INK_HEX = ACCENT_HEX = TINT = RULE = BAND = None   # 'RRGGBB'
FONT_BODY = FONT_HEADING = FONT_MONO = None
MARGINS = {}


def _hex(value):
    h = value.lstrip('#').upper()
    if len(h) != 6 or any(c not in '0123456789ABCDEF' for c in h):
        raise ValueError(f"not a 6-digit hex color: {value!r}")
    return h


def _mix(hex_color, other, ratio):
    """Blend hex_color toward other (both 'RRGGBB') by ratio, 0..1."""
    a = [int(hex_color[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(other[i:i + 2], 16) for i in (0, 2, 4)]
    return ''.join(f"{round(x + (y - x) * ratio):02X}" for x, y in zip(a, b))


def load_tokens(path):
    global INK, ACCENT, MUTED, INK_HEX, ACCENT_HEX, TINT, RULE, BAND
    global FONT_BODY, FONT_HEADING, FONT_MONO, MARGINS
    t = json.loads(Path(path).read_text())
    c = t["colors"]
    INK_HEX, ACCENT_HEX, muted_hex = _hex(c["ink"]), _hex(c["accent"]), _hex(c["muted"])
    INK, ACCENT, MUTED = (RGBColor.from_string(h) for h in (INK_HEX, ACCENT_HEX, muted_hex))
    TINT = _hex(c["tint"]) if c.get("tint") else _mix(ACCENT_HEX, "FFFFFF", 0.9)
    RULE = _hex(c["rule"]) if c.get("rule") else _mix(INK_HEX, "FFFFFF", 0.85)
    BAND = _hex(c["band"]) if c.get("band") else _mix(INK_HEX, "FFFFFF", 0.93)
    f = t["fonts"]
    FONT_BODY, FONT_HEADING = f["body"], f.get("heading", f["body"])
    FONT_MONO = f.get("mono", "Consolas")
    m = t.get("margins_cm", {})
    MARGINS = {k: m.get(k, v) for k, v in
               {"top": 2.2, "bottom": 2.2, "left": 2.4, "right": 2.4}.items()}


def set_font(style, name, size=None, bold=None, color=None, italic=None):
    font = style.font
    font.name = name
    rpr = style.element.get_or_add_rPr()
    rFonts = rpr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = docx.oxml.OxmlElement('w:rFonts')
        rpr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), name)
    rFonts.set(qn('w:ascii'), name)
    rFonts.set(qn('w:hAnsi'), name)
    if size is not None:
        font.size = Pt(size)
    if bold is not None:
        font.bold = bold
    if italic is not None:
        font.italic = italic
    if color is not None:
        font.color.rgb = color


def find_pandoc():
    """$PANDOC, then PATH, then a static binary at assets/bin/pandoc."""
    for candidate in (os.environ.get("PANDOC"), shutil.which("pandoc"), str(HERE / "bin" / "pandoc")):
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    sys.exit("pandoc not found. Install it with your package manager, or download a static binary from "
             "https://github.com/jgm/pandoc/releases and set PANDOC=/path/to/pandoc "
             f"(or place it at {HERE / 'bin' / 'pandoc'}).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tokens', default=str(HERE / 'tokens.json'))
    ap.add_argument('--out', default=str(HERE / 'reference.docx'))
    args = ap.parse_args()
    load_tokens(args.tokens)
    output_docx = Path(args.out)

    # Always start from a fresh copy of pandoc's own default reference.docx,
    # so this script stays correct even if pandoc changes its base styles.
    result = subprocess.run(
        [find_pandoc(), "-o", str(BASE_DOCX), "--print-default-data-file", "reference.docx"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("pandoc failed to produce the base reference.docx:", result.stderr, file=sys.stderr)
        sys.exit(1)

    d = docx.Document(str(BASE_DOCX))
    styles = d.styles

    # Body text
    normal = styles['Normal']
    set_font(normal, FONT_BODY, 11, color=INK)
    normal.paragraph_format.space_after = Pt(10)
    normal.paragraph_format.line_spacing = 1.25

    # Title / Subtitle — kept for completeness, but unused by the skill's normal
    # workflow: it relies on the markdown's own single H1 as the document title
    # (see SKILL.md) rather than pandoc title-block metadata, to avoid a
    # duplicate title.
    title = styles['Title']
    set_font(title, FONT_HEADING, 28, bold=False, color=INK)
    try:
        subtitle = styles['Subtitle']
        set_font(subtitle, FONT_BODY, 13, bold=False, color=MUTED)
    except KeyError:
        pass

    # Heading 1 doubles as the document title — centered, with a thin accent
    # rule underneath standing in for a title-block underline.
    h1 = styles['Heading 1']
    set_font(h1, FONT_HEADING, 26, bold=True, color=INK)
    h1.paragraph_format.space_before = Pt(0)
    h1.paragraph_format.space_after = Pt(18)
    h1.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pPr = h1.element.get_or_add_pPr()
    pBdr = docx.oxml.OxmlElement('w:pBdr')
    bottom = docx.oxml.OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '8')
    bottom.set(qn('w:color'), ACCENT_HEX)
    pBdr.append(bottom)
    pPr.append(pBdr)

    # Heading 2 — section headers
    h2 = styles['Heading 2']
    set_font(h2, FONT_BODY, 15, bold=True, color=ACCENT)
    h2.paragraph_format.space_before = Pt(22)
    h2.paragraph_format.space_after = Pt(8)

    # Heading 3 — sub-section headers
    h3 = styles['Heading 3']
    set_font(h3, FONT_BODY, 12, bold=True, color=MUTED)
    h3.paragraph_format.space_before = Pt(14)
    h3.paragraph_format.space_after = Pt(4)

    # Heading 4 / Heading 5 — deeper nesting, used by longer reports with
    # numbered steps under a section. Pandoc's base reference.docx leaves
    # these a Word-default blue (and H4 italic), which reads as off-theme
    # next to the ink/accent/muted palette above. Keep them in-palette and
    # visibly subordinate to H3: H4 ink and bold, H5 muted and bold at body
    # size. Documents with no H4/H5 are unaffected.
    h4 = styles['Heading 4']
    set_font(h4, FONT_BODY, 11.5, bold=True, color=INK)
    h4.paragraph_format.space_before = Pt(12)
    h4.paragraph_format.space_after = Pt(3)
    h4.font.italic = False

    try:
        h5 = styles['Heading 5']
        set_font(h5, FONT_BODY, 11, bold=True, color=MUTED)
        h5.paragraph_format.space_before = Pt(10)
        h5.paragraph_format.space_after = Pt(2)
        h5.font.italic = False
    except KeyError:
        pass

    # Source Code — pandoc CREATES a "SourceCode" paragraph style in its output
    # when the reference doc has none, which silently leaves code blocks at body
    # size. Define it here so the theme owns it. python-docx maps the style name
    # "Source Code" to the styleId "SourceCode" that pandoc looks for.
    try:
        src = styles['Source Code']
    except KeyError:
        src = styles.add_style('Source Code', WD_STYLE_TYPE.PARAGRAPH)
    set_font(src, FONT_MONO, 8.5, color=INK)
    src.paragraph_format.space_before = Pt(0)
    src.paragraph_format.space_after = Pt(0)
    src.paragraph_format.line_spacing = 1.0
    src.paragraph_format.left_indent = Cm(0.35)
    sPr = src.element.get_or_add_pPr()
    sBdr = docx.oxml.OxmlElement('w:pBdr')
    sLeft = docx.oxml.OxmlElement('w:left')
    sLeft.set(qn('w:val'), 'single')
    sLeft.set(qn('w:sz'), '12')
    sLeft.set(qn('w:space'), '8')
    sLeft.set(qn('w:color'), RULE)
    sBdr.append(sLeft)
    sPr.append(sBdr)

    # Verbatim Char — inline code. Slightly under body size so it does not
    # dominate a sentence, but large enough to stay legible.
    try:
        vc = styles['Verbatim Char']
        set_font(vc, FONT_MONO, 9.5, color=INK)
    except KeyError:
        pass

    # Block Text — pandoc's blockquote style, used by this theme as a callout
    # (a one-line summary under a heading). Left accent rule plus muted italic,
    # so it reads as a callout rather than plain indented body copy.
    try:
        bt = styles['Block Text']
        set_font(bt, FONT_BODY, 10.5, color=MUTED, italic=True)
        bt.paragraph_format.left_indent = Cm(0.35)
        bt.paragraph_format.space_before = Pt(4)
        bt.paragraph_format.space_after = Pt(8)
        bt.paragraph_format.line_spacing = 1.15
        bPr = bt.element.get_or_add_pPr()
        bBdr = docx.oxml.OxmlElement('w:pBdr')
        bLeft = docx.oxml.OxmlElement('w:left')
        bLeft.set(qn('w:val'), 'single')
        bLeft.set(qn('w:sz'), '18')
        bLeft.set(qn('w:space'), '8')
        bLeft.set(qn('w:color'), ACCENT_HEX)
        bBdr.append(bLeft)
        bPr.append(bBdr)
    except KeyError:
        pass

    # Table — pandoc emits tblLook firstRow="1" noHBand="0", so firstRow and
    # band2Horz conditional formats are what style the header row and the
    # alternating body rows. The base style already has a firstRow element
    # carrying only a bottom border; extend that one rather than appending a
    # second, which Word would not merge. No borders anywhere.
    try:
        tbl = styles['Table']

        # no table or cell borders
        tblPr = tbl.element.find(qn('w:tblPr'))
        if tblPr is None:
            tblPr = docx.oxml.OxmlElement('w:tblPr')
            tbl.element.append(tblPr)
        band_size = docx.oxml.OxmlElement('w:tblStyleRowBandSize')
        band_size.set(qn('w:val'), '1')
        tblPr.insert(0, band_size)
        borders = docx.oxml.OxmlElement('w:tblBorders')
        for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            b = docx.oxml.OxmlElement(f'w:{side}')
            b.set(qn('w:val'), 'nil')
            borders.append(b)
        # schema order: tblStyleRowBandSize, ..., tblInd, tblBorders, ..., tblCellMar
        cell_mar = tblPr.find(qn('w:tblCellMar'))
        if cell_mar is not None:
            cell_mar.addprevious(borders)
        else:
            tblPr.append(borders)

        firstRow = None
        for el in tbl.element.findall(qn('w:tblStylePr')):
            if el.get(qn('w:type')) == 'firstRow':
                firstRow = el
                break
        if firstRow is None:
            firstRow = docx.oxml.OxmlElement('w:tblStylePr')
            firstRow.set(qn('w:type'), 'firstRow')
            tbl.element.append(firstRow)

        # bold, ink header text
        rPr = firstRow.find(qn('w:rPr'))
        if rPr is None:
            rPr = docx.oxml.OxmlElement('w:rPr')
            firstRow.insert(0, rPr)
        bold = docx.oxml.OxmlElement('w:b')
        rPr.append(bold)
        tcol = docx.oxml.OxmlElement('w:color')
        tcol.set(qn('w:val'), INK_HEX)
        rPr.append(tcol)

        # tinted header fill, dropping the base bottom border
        tcPr = firstRow.find(qn('w:tcPr'))
        if tcPr is None:
            tcPr = docx.oxml.OxmlElement('w:tcPr')
            firstRow.append(tcPr)
        for old in tcPr.findall(qn('w:tcBorders')):
            tcPr.remove(old)
        shd = docx.oxml.OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), TINT)
        tcPr.insert(0, shd)

        # alternating body rows: the first row below the header stays white,
        # every second row gets the band fill
        band = docx.oxml.OxmlElement('w:tblStylePr')
        band.set(qn('w:type'), 'band2Horz')
        bandPr = docx.oxml.OxmlElement('w:tcPr')
        bshd = docx.oxml.OxmlElement('w:shd')
        bshd.set(qn('w:val'), 'clear')
        bshd.set(qn('w:color'), 'auto')
        bshd.set(qn('w:fill'), BAND)
        bandPr.append(bshd)
        band.append(bandPr)
        tbl.element.append(band)
    except KeyError:
        pass

    # List Bullet — some pandoc/Word combinations render bullets via this
    # style rather than Compact; style both to be safe.
    try:
        lb = styles['List Bullet']
        set_font(lb, FONT_BODY, 11, color=INK)
        lb.paragraph_format.space_after = Pt(4)
    except KeyError:
        pass

    # Compact — pandoc's actual tight-list-item style for bullets/numbers.
    # Left-aligned: an earlier version of this theme accidentally centered
    # this style while trying to center figures, which centered every bullet
    # in the document. Keep this left-aligned.
    try:
        compact = styles['Compact']
        set_font(compact, FONT_BODY, 11, color=INK)
        compact.paragraph_format.space_after = Pt(4)
    except KeyError:
        pass

    # Image Caption — the caption text pandoc renders below a figure.
    try:
        cap = styles['Image Caption']
        set_font(cap, FONT_BODY, 9, italic=True, color=MUTED)
        cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_before = Pt(4)
        cap.paragraph_format.space_after = Pt(16)
    except KeyError:
        pass

    # Captioned Figure — the paragraph wrapping the inserted image itself.
    # This is the style that actually needs centering for a centered figure.
    try:
        figstyle = styles['Captioned Figure']
        figstyle.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        figstyle.paragraph_format.space_before = Pt(6)
        figstyle.paragraph_format.space_after = Pt(2)
    except KeyError:
        pass

    # Page margins
    section = d.sections[0]
    section.top_margin = Cm(MARGINS['top'])
    section.bottom_margin = Cm(MARGINS['bottom'])
    section.left_margin = Cm(MARGINS['left'])
    section.right_margin = Cm(MARGINS['right'])

    d.save(str(output_docx))
    BASE_DOCX.unlink(missing_ok=True)
    print(f"saved {output_docx}")


if __name__ == "__main__":
    main()
