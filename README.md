# docs-for-claude

Claude Code plugin that converts markdown documents (case studies, reports) to styled `.docx` and PDF files.

## Contents

| Skill | Purpose |
|---|---|
| `render-themed-docs` | Renders markdown to `.docx` and PDF with a theme from `tokens.json`: title with accent rule, colored section headings, left-aligned bullets, captioned figures. Can infer the tokens from Figma, CSS, design-token JSON or an existing `.docx`. |

## Requirements

- [pandoc](https://pandoc.org/), from a package manager or a [static binary](https://github.com/jgm/pandoc/releases). The scripts use `$PANDOC`, then `PATH`, then `skills/render-themed-docs/assets/bin/pandoc`.
- Python 3 (standard library only), for `hide_bookmarks.py`
- For PDF output, one of: LibreOffice (`soffice`), or the `typst` Python package (`pip install typst`)
- Optional, for visual verification: PyMuPDF
- Optional, to regenerate the theme: Python 3 with `python-docx`

## Install

```
/plugin marketplace add realbucksavage/docs-for-claude
/plugin install docs-for-claude@docs-for-claude
```

## Theme

Colors, fonts and margins are in `skills/render-themed-docs/assets/tokens.json`. Run `build_reference_docx.py` to regenerate `reference.docx` after editing it. `extract_tokens.py` infers a `tokens.json` from a Figma export, CSS/HTML, a design-token JSON or an existing `.docx`; see `references/infer-tokens.md`. Sizes and spacing are in `build_reference_docx.py`. Design tokens are listed in `skills/render-themed-docs/references/theme-spec.md`.

## License

MIT. See `LICENSE`.
