# Theme design tokens

The values in `assets/tokens.json` (colors, fonts, margins) and `assets/build_reference_docx.py` (sizes, spacing) apply to pandoc's default `reference.docx`. Read this before changing a color, font, or spacing value, so an edit stays consistent across every style it touches.

| Role | Value |
|---|---|
| Ink (body text, title) | `#2D3142` |
| Accent (H2 headers, title rule) | `#C0521E` |
| Muted (H3 headers, captions) | `#4F5D75` |
| Body font | Calibri, 11pt, 1.25 line spacing |
| Title font | Calibri Light, 26pt, bold, centered, ink, thin accent-colored rule beneath (via `w:pBdr`/`w:bottom` on Heading 1) |
| H2 (section) font | Calibri, 15pt, bold, accent |
| H3 (sub-section) font | Calibri, 12pt, bold, muted |
| Bullets (`Compact`, `List Bullet`) | Calibri, 11pt, ink, left-aligned |
| Tables (`Table`) | no borders; header row bold, ink, tint fill; every second body row band fill (`colors.band`, default ink blended 93% toward white) |
| Figure (`Captioned Figure`) | centered |
| Figure caption (`Image Caption`) | Calibri, 9pt, italic, muted, centered |
| Page margins | 2.2cm top/bottom, 2.4cm left/right |

## Why Heading 1 doubles as the title

Pandoc's `Title`/`Subtitle` styles come from YAML front-matter or `--metadata title=...`. Passing that metadata alongside a markdown file that also starts with a single `#` H1 produces two titles stacked on top of each other — the metadata title block, then the H1 rendered again as a Heading 1 paragraph. Case studies built for this theme are expected to have exactly one H1 (the document title) and no pandoc title metadata; Heading 1 is styled to look like a title (centered, larger, rule underneath) instead. If a source markdown file has no H1 at all, consider passing `--metadata title=...` instead, and note the `Title` style is still styled correctly as a fallback.

## Why `Compact`, not `List Bullet`, controls bullet alignment

Pandoc's docx writer renders tight (non-loose) list items — the common case for a bulleted list in a case study — using its `Compact` paragraph style, not `List Bullet`. An earlier version of this theme accidentally centered `Compact` while intending to center image paragraphs, which silently centered every bullet in the document. Both styles are set explicitly now to avoid that ambiguity resurfacing: `Compact` is left-aligned for bullets, `Captioned Figure` is centered for images.

## Regenerating the theme

Run `python3 assets/build_reference_docx.py [--tokens tokens.json] [--out reference.docx]` (needs `pandoc` on PATH and the `python-docx` package). It always starts from a fresh `pandoc --print-default-data-file reference.docx`, so it stays correct even if a pandoc upgrade changes the built-in base styles — you're never patching last year's reference.docx in place.
