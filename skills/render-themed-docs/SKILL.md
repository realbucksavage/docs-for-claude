---
name: render-themed-docs
description: Renders a markdown file to a themed .docx and/or PDF using pandoc and a theme defined in tokens.json (colors, fonts, margins; centered title with accent rule, accent-colored section headings, muted sub-headings, left-aligned bullets, captioned figures). PDFs are produced with LibreOffice or, without it, Typst. Use whenever the user asks to render, export or convert markdown to .docx, Word or PDF, or wants a report, case study or other write-up in a consistent, finished format rather than bare pandoc output. Also use to re-theme an existing document, to apply "the same theme as before" to a new file, or to build the theme from a Figma file, CSS, design-token JSON or existing .docx.
---

# render-themed-docs

Turns a markdown file into a `.docx` or PDF styled with this skill's theme. The `.docx` uses pandoc's `--reference-doc` mechanism. The theme lives as a ready-to-use `reference.docx` bundled in `assets/` — you don't regenerate it on every run, just point pandoc at it.

## When to reach for this vs. plain pandoc

Use this skill instead of a bare `pandoc file.md -o file.docx` whenever the output is meant to be read outside the terminal, for example by a client or stakeholder. Plain pandoc output uses Word's default styles (small serif body text, blue Heading 1). This theme applies the same colors, fonts and heading styles to every document, so output from different sessions looks consistent.

## If pandoc is not installed

`render.sh` and the Python scripts look for pandoc in this order: `$PANDOC`, `PATH`, `assets/bin/pandoc`. `render.sh` exits with status 127 when none is found. In that case:

1. Detect the package manager (`brew`, `apt-get`, `dnf`, `pacman`, `zypper`, `apk`, `winget`, `choco`, `scoop`, `conda`) and offer the matching install command (for example `brew install pandoc` or `sudo apt-get install pandoc`). Run it only after the user agrees; commands that need `sudo` or an interactive login are for the user to run with `! <command>`.
2. If the user has no package manager, cannot install, or declines, ask them to download a static build from <https://github.com/jgm/pandoc/releases> (macOS: the `.zip` for their CPU; Linux: the `linux-amd64` or `linux-arm64` `.tar.gz`; Windows: the `.zip`). Ask for the path of the extracted `pandoc` executable, then run with `PANDOC=<path>` set. They can instead copy it to `assets/bin/pandoc` so it is found automatically; that path is git-ignored.
3. Check the binary with `<path> --version` before using it. Do not download binaries yourself.

## Conversion command

```bash
pandoc "<input.md>" \
  --from=markdown+smart \
  --to=docx \
  --reference-doc="<this-skill-dir>/assets/reference.docx" \
  --resource-path="<directory containing input.md>" \
  -o "<output.docx>"
```

Notes:

- `--resource-path` matters whenever the markdown references images with relative paths (`![...](images/diagram.png)`) — set it to the markdown file's own directory (or wherever those relative paths should resolve from) or the images won't be found.
- `--from=markdown+smart` turns straight quotes/hyphens into typographic ones (curly quotes, em dashes) — worth keeping for a document meant to look finished.
- Find `<this-skill-dir>` from wherever this SKILL.md is loaded from (for a plugin install, under the plugin's `skills/render-themed-docs/` directory).

## PDF output

`assets/render.sh` produces the `.docx`, the PDF, or both:

```bash
"<this-skill-dir>/assets/render.sh" "<input.md>" pdf  [output-dir] [engine]   # PDF only
"<this-skill-dir>/assets/render.sh" "<input.md>" both [output-dir] [engine]   # .docx and PDF
```

`engine` is `auto` (default), `soffice` or `typst`:

- **soffice** converts the themed `.docx` with LibreOffice, so the PDF matches the Word output exactly.
- **typst** renders directly from `assets/tokens.json` through `assets/render_pdf_typst.py` (pandoc's Typst writer plus the Typst compiler). It needs only `pip install typst` (or a `typst` binary), not LibreOffice. Colors, fonts, margins and heading/table/code/callout/figure styling match the theme; line breaks and spacing can differ slightly from Word.
- **auto** uses `soffice` if installed, otherwise `typst`. If neither exists, the script exits with install instructions. When that happens, offer to run `pip install typst` for the user or deliver the `.docx` alone; do not install anything without asking.

The theme uses Calibri and Calibri Light. If a font is not installed, both engines substitute another font (Carlito, Helvetica Neue, Arial or similar), which can shift line breaks. Use the PDF for the verification steps below.

## Markdown authoring conventions this theme expects

The theme styles pandoc's own docx output styles directly (Heading 1/2/3, Compact, Captioned Figure, Image Caption, etc.) — no pandoc filter or Lua script involved. For it to look right:

- **Exactly one `# H1`, at the top of the file, as the document title.** Heading 1 is styled to *be* the title (centered, larger, with a rule underneath) — see `references/theme-spec.md` for why. Don't also pass `--metadata title=...`; that produces a second, duplicate title above the H1.
- **`## H2` for section headers**, **`### H3`** for sub-sections within a section.
- **Images with alt text become captioned figures automatically** — `![Alt text describing the figure](path.png)` on its own line renders as a centered image with the alt text as an italic caption underneath. Write real, descriptive alt text; it becomes visible caption copy, not just an accessibility attribute.
- Bullet lists render left-aligned automatically — no special authoring needed there.

## After converting, verify — don't just trust the file was written

`pandoc` exiting 0 doesn't mean the document reads well: image paths can silently fail to resolve, a stray title-metadata flag can duplicate the title, a style tweak can misfire (see the `Compact` alignment story in `references/theme-spec.md` — that exact bug happened once). Before handing the file back:

1. Convert to PDF (skip if the PDF was the requested output): `soffice --headless --convert-to pdf "<output.docx>" --outdir <some-dir>` (LibreOffice; confirm it's installed first).
2. Rasterize at least the first page (and any page with an image) with PyMuPDF:
   ```python
   import fitz
   doc = fitz.open("<output.pdf>")
   for i, p in enumerate(doc):
       p.get_pixmap(dpi=110).save(f"page{i+1}.png")
   ```
   (`python3 -m pip install --quiet pymupdf` first if the import fails.)
3. Read the resulting PNG(s) and actually look — check the title isn't duplicated, bullets are left-aligned, images resolved and are centered with captions, heading colors match the theme.

## Matching an existing brand or theme

To build the theme from a Figma file, a CSS/HTML stylesheet, a design-token JSON or an existing .docx, follow `references/infer-tokens.md`. It produces a `tokens.json` that `build_reference_docx.py --tokens` turns into a `reference.docx`. Confirm the result with the user before replacing the bundled theme.

## Tweaking or regenerating the theme

Colors, fonts and margins are in `assets/tokens.json`; edit that and re-run the build script. Don't hand-edit `assets/reference.docx`'s XML. For anything beyond those tokens, edit `assets/build_reference_docx.py` (which owns the remaining style decisions) and re-run it — see `references/theme-spec.md` for the full token table (colors, fonts, sizes, margins) and the reasoning behind a couple of non-obvious choices before changing anything.
