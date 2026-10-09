# Inferring theme tokens from an existing design

The theme is driven by `assets/tokens.json` (colors, fonts, page margins). To match an existing brand or document, produce a `tokens.json` from that source, then rebuild `reference.docx`.

## Token roles

| Token | Used for |
|---|---|
| `colors.ink` | body text, title, H4, table header text |
| `colors.accent` | H2, title rule, callout rule |
| `colors.muted` | H3, H5, captions, callout text |
| `colors.tint` (optional) | table header fill. Default: accent blended 90% toward white |
| `colors.rule` (optional) | code-block left rule. Default: ink blended 85% toward white |
| `fonts.body` / `fonts.heading` / `fonts.mono` | body and lists / title and H1 / code |
| `margins_cm.top/bottom/left/right` | page margins |

Font sizes and spacing are not tokens; they stay in `build_reference_docx.py`.

## Procedure

1. Get the source into a local file (see below).
2. Run `python3 assets/extract_tokens.py <docx|css|json> <source> --out <work-dir>/tokens.json`. The script lists each inferred value with its origin, names tokens it could not find (defaults are kept), and warns when ink, accent or muted is below 4.5:1 contrast on white.
3. Review the report. Role assignment is a heuristic: confirm that accent is the brand color and that ink is the body text color. Edit the JSON if not.
4. Build: `python3 assets/build_reference_docx.py --tokens <work-dir>/tokens.json --out <work-dir>/reference.docx`.
5. Render a sample and check the PDF visually. `.docx` output uses `--reference-doc=<work-dir>/reference.docx`; the Typst PDF engine reads colors and fonts with `python3 assets/render_pdf_typst.py <in.md> <out.pdf> --tokens <work-dir>/tokens.json`. See the verification steps in `SKILL.md`.
6. To make the theme permanent, copy the JSON over `assets/tokens.json` and run `build_reference_docx.py` without arguments.

Do not overwrite `assets/tokens.json` or `assets/reference.docx` until the user confirms the result.

## Sources

**Existing .docx or .dotx.** `extract_tokens.py docx file.docx`. Reads Normal (ink, body font), Heading 2 (accent), Heading 3 or Caption (muted), Heading 1 (heading font) and the first section's margins. Fonts defined only through a Word theme are not resolved; set them by hand.

**CSS or HTML.** `extract_tokens.py css site.css` (or an `.html` file with `<style>` blocks). Reads custom properties by name (`--text`, `--primary`, `--muted`, `--border`, `--font-heading`, ...) and the `body`, `h2`, `h3`, `h1`, `code` rules. Rules take precedence over variable names. For a live site, download the stylesheet to a file first.

**Design-token JSON.** `extract_tokens.py json tokens.json`. Accepts W3C design-tokens files (`$value`/`$type`) and similar nested JSON. If no color name matches the accent role, the most saturated mid-luminance color is used and the report says so.

**Figma.** The extractor does not call Figma. Fetch the data with the Figma MCP tools, write it to a JSON file, then use the `json` source.

1. If the Figma tools report they need authentication, ask the user to authenticate the Figma connector.
2. Get the file's local variables (color and string variables, including font-family variables) and its text and fill styles. If the user gave a frame or node, read that node's text styles and fills instead.
3. Save the result as JSON. Keep variable names, since the extractor matches roles by name (`text/primary`, `brand/accent`, `text/muted`, `font/heading`). Figma colors given as `{r,g,b}` in 0..1 are accepted.
4. If the file has no variables and only unnamed fills, choose roles yourself from usage: the heading fill that is not black is the accent, the body text fill is ink, and the lighter caption or secondary text fill is muted. Write `tokens.json` directly and tell the user which node each value came from.

Fonts must be installed on the machine that renders the document, or Word and LibreOffice substitute another font. Tell the user if a font from the source is likely not installed.
