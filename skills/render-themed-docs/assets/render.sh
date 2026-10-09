#!/usr/bin/env bash
# Render a markdown file with the theme to .docx and/or .pdf.
# Usage: render.sh <input.md> [docx|pdf|both] [output-dir] [auto|soffice|typst]
#
# The .docx is built with pandoc and reference.docx.
# pandoc is taken from $PANDOC, PATH, or assets/bin/pandoc; exit status 127 means it was not found.
# PDF engines:
#   soffice  converts the themed .docx with LibreOffice (exact match with the .docx)
#   typst    renders from tokens.json via pandoc's Typst writer; needs only
#            `pip install typst` (or a typst binary), not LibreOffice
#   auto     (default) soffice if installed, otherwise typst
set -euo pipefail

input="${1:?usage: render.sh <input.md> [docx|pdf|both] [output-dir] [auto|soffice|typst]}"
format="${2:-docx}"
engine="${4:-auto}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src_dir="$(cd "$(dirname "$input")" && pwd)"
outdir="${3:-$src_dir}"
base="$(basename "${input%.*}")"

case "$format" in docx|pdf|both) ;; *) echo "format must be docx, pdf or both" >&2; exit 2;; esac
case "$engine" in auto|soffice|typst) ;; *) echo "engine must be auto, soffice or typst" >&2; exit 2;; esac

# pandoc lookup: $PANDOC, then PATH, then a static binary at assets/bin/pandoc.
if [ -n "${PANDOC:-}" ]; then :
elif command -v pandoc >/dev/null; then PANDOC="$(command -v pandoc)"
elif [ -x "$here/bin/pandoc" ]; then PANDOC="$here/bin/pandoc"
else
  echo "pandoc not found. Install it with your package manager, or download a static binary from https://github.com/jgm/pandoc/releases and set PANDOC=/path/to/pandoc (or place it at $here/bin/pandoc)." >&2
  exit 127
fi
[ -x "$PANDOC" ] || { echo "PANDOC=$PANDOC is not an executable file" >&2; exit 127; }
export PANDOC

mkdir -p "$outdir"

soffice_bin="$(command -v soffice || command -v libreoffice || true)"
have_typst() { python3 -c "import typst" 2>/dev/null || command -v typst >/dev/null; }

if [ "$format" != "docx" ]; then
  if [ "$engine" = "auto" ]; then
    if [ -n "$soffice_bin" ]; then engine=soffice
    elif have_typst; then engine=typst
    else
      echo "No PDF engine found. Install one of: LibreOffice (soffice), or Typst via 'pip install typst'." >&2
      exit 1
    fi
  fi
  [ "$engine" = "soffice" ] && [ -z "$soffice_bin" ] && { echo "LibreOffice (soffice) not found" >&2; exit 1; }
  [ "$engine" = "typst" ] && ! have_typst && { echo "Typst not found; install with 'pip install typst'" >&2; exit 1; }
fi

# .docx is needed for docx/both output and for the soffice PDF route.
if [ "$format" != "pdf" ] || [ "${engine}" = "soffice" ]; then
  docx="$outdir/$base.docx"
  "$PANDOC" "$input" \
    --from=markdown+smart --to=docx \
    --reference-doc="$here/reference.docx" \
    --resource-path="$src_dir" \
    -o "$docx"
fi

if [ "$format" != "docx" ]; then
  if [ "$engine" = "soffice" ]; then
    "$soffice_bin" --headless --convert-to pdf "$docx" --outdir "$outdir" >/dev/null
    if [ "$format" = "pdf" ]; then rm -f "$docx"; fi
  else
    python3 "$here/render_pdf_typst.py" "$input" "$outdir/$base.pdf"
  fi
fi
