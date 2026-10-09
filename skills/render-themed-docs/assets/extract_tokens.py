"""
Infers theme tokens (tokens.json) from an existing design source.

Usage:
    python3 extract_tokens.py docx  <file.docx>        [--out tokens.json]
    python3 extract_tokens.py css   <file.css|file.html> [--out tokens.json]
    python3 extract_tokens.py json  <tokens-or-variables.json> [--out tokens.json]

Sources:
  docx  Styles of an existing Word document or template (Normal, Heading 1-3,
        Caption, page margins).
  css   CSS custom properties plus body/h1-h3/code rules, from a .css file or
        the <style> blocks of an .html file.
  json  A W3C design-tokens file or a Figma variables / styles export (any
        nested JSON in which colors are "#rrggbb" strings and fonts are named).
        Figma data is fetched through the Figma MCP tools and saved to a file
        first; see references/infer-tokens.md.

Each token is reported with where it came from. Tokens the source does not
provide keep the defaults from tokens.json. Review the report before using the
output; role assignment (ink/accent/muted) is a heuristic.
"""
import argparse
import colorsys
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HEX_RE = re.compile(r'^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$')

# Name fragments that indicate a role. Checked in order; first match wins.
ROLE_HINTS = {
    "muted": ("muted", "secondary", "subtle", "caption", "gray", "grey", "neutral-6", "text-light"),
    "ink": ("ink", "foreground", "text", "body", "fg", "on-surface", "neutral-9", "black"),
    "accent": ("accent", "primary", "brand", "highlight", "link"),
    "tint": ("tint", "surface-alt", "background-alt", "bg-alt", "table-header"),
    "rule": ("rule", "border", "divider", "outline", "stroke"),
}
FONT_HINTS = {
    "mono": ("mono", "code"),
    "heading": ("heading", "display", "title", "headline"),
    "body": ("body", "text", "base", "sans", "primary"),
}


def norm_hex(value):
    m = HEX_RE.match(value.strip())
    if not m:
        return None
    h = m.group(1).upper()
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return '#' + h


def rgb_to_hex(r, g, b):
    return '#%02X%02X%02X' % tuple(round(x) for x in (r, g, b))


def luminance(h):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def saturation(h):
    r, g, b = (int(h.lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)[2]


def classify(name, hints):
    n = name.lower()
    for role, words in hints.items():
        if any(w in n for w in words):
            return role
    return None


def first_font(family):
    """First family name from a CSS font-family list, skipping generic keywords."""
    for part in family.split(','):
        p = part.strip().strip('"\'')
        if p and p.lower() not in ("sans-serif", "serif", "monospace", "system-ui", "inherit",
                                    "-apple-system", "blinkmacsystemfont", "ui-sans-serif",
                                    "ui-monospace", "ui-serif"):
            return p
    return None


def from_docx(path):
    import docx
    d = docx.Document(path)
    found = {}

    def style_font(style):
        s = style
        while s is not None:
            if s.font.name:
                return s.font.name
            s = s.base_style
        return None

    def style_color(style):
        s = style
        while s is not None:
            if s.font.color is not None and s.font.color.type is not None and s.font.color.rgb is not None:
                return '#' + str(s.font.color.rgb)
            s = s.base_style
        return None

    names = {s.name: s for s in d.styles}
    for token, style_name in (("ink", "Normal"), ("accent", "Heading 2"), ("muted", "Heading 3")):
        st = names.get(style_name)
        col = style_color(st) if st else None
        if col:
            found[("colors", token)] = (col, f"docx style '{style_name}' color")
    cap = names.get("Caption")
    if cap and style_color(cap) and ("colors", "muted") not in found:
        found[("colors", "muted")] = (style_color(cap), "docx style 'Caption' color")
    for token, style_name in (("body", "Normal"), ("heading", "Heading 1")):
        st = names.get(style_name)
        f = style_font(st) if st else None
        if f:
            found[("fonts", token)] = (f, f"docx style '{style_name}' font")
    sec = d.sections[0]
    for side in ("top", "bottom", "left", "right"):
        v = getattr(sec, f"{side}_margin")
        if v is not None:
            found[("margins_cm", side)] = (round(v.cm, 2), "docx page margin")
    return found


def from_css(path):
    text = Path(path).read_text(errors="ignore")
    if path.lower().endswith((".html", ".htm")):
        text = '\n'.join(re.findall(r'<style[^>]*>(.*?)</style>', text, re.S | re.I))
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    found = {}

    # Custom properties, classified by name.
    for name, value in re.findall(r'(--[\w-]+)\s*:\s*([^;}]+)', text):
        hx = norm_hex(value)
        if hx:
            role = classify(name, {k: v for k, v in ROLE_HINTS.items()})
            if role and ("colors", role) not in found:
                found[("colors", role)] = (hx, f"css variable {name}")
        elif 'font' in name.lower() or ',' in value:
            fam = first_font(value)
            role = classify(name, FONT_HINTS) if fam else None
            if role and ("fonts", role) not in found:
                found[("fonts", role)] = (fam, f"css variable {name}")

    # Element rules, which override variable-name guesses for the roles they define.
    def rule(selector):
        m = re.search(r'(?:^|[}\s,])' + selector + r'\s*(?:,[^{]*)?\{([^}]*)\}', text, re.S)
        return m.group(1) if m else ''

    def prop(block, name):
        m = re.search(r'(?:^|;|\s)' + name + r'\s*:\s*([^;]+)', block)
        return m.group(1).strip() if m else None

    for token, sel in (("ink", "body"), ("accent", "h2"), ("muted", "h3")):
        col = prop(rule(sel), "color")
        hx = norm_hex(col) if col else None
        if hx:
            found[("colors", token)] = (hx, f"css rule {sel} color")
    for token, sel in (("body", "body"), ("heading", "h1"), ("mono", "code")):
        fam = prop(rule(sel), "font-family")
        f = first_font(fam) if fam else None
        if f:
            found[("fonts", token)] = (f, f"css rule {sel} font-family")
    return found


def walk_json(node, path=()):
    """Yield (path, value, type) for leaves in a nested token tree."""
    if isinstance(node, dict):
        if "$value" in node or "value" in node:
            yield path, node.get("$value", node.get("value")), node.get("$type", node.get("type"))
        else:
            for k, v in node.items():
                yield from walk_json(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_json(v, path + (str(i),))
    else:
        yield path, node, None


def figma_color(v):
    """Figma colors may be {r,g,b,a} in 0..1."""
    if isinstance(v, dict) and all(k in v for k in "rgb"):
        return rgb_to_hex(v["r"] * 255, v["g"] * 255, v["b"] * 255)
    return None


def from_json(path):
    data = json.loads(Path(path).read_text())
    found = {}
    colors = []
    for p, value, typ in walk_json(data):
        name = '/'.join(p)
        hx = norm_hex(value) if isinstance(value, str) else figma_color(value)
        if hx:
            colors.append((name, hx))
            role = classify(name, ROLE_HINTS)
            if role and ("colors", role) not in found:
                found[("colors", role)] = (hx, f"token {name}")
        elif isinstance(value, str) and (typ in ("fontFamily", "fontFamilies") or 'font' in name.lower()
                                         and 'size' not in name.lower() and 'weight' not in name.lower()):
            fam = first_font(value)
            role = classify(name, FONT_HINTS) if fam else None
            if role and ("fonts", role) not in found:
                found[("fonts", role)] = (fam, f"token {name}")
    # Brand colors are often named by hue ("orange-600") only. If no accent was
    # found by name, take the most saturated color that is not near black/white.
    if ("colors", "accent") not in found and colors:
        cands = [c for c in colors if 0.15 < luminance(c[1]) < 0.7]
        if cands:
            name, hx = max(cands, key=lambda c: saturation(c[1]))
            found[("colors", "accent")] = (hx, f"token {name} (most saturated; no role name matched)")
    return found


def merge(found):
    out = json.loads((HERE / "tokens.json").read_text())
    report = []
    for (group, key), (value, src) in sorted(found.items()):
        out.setdefault(group, {})[key] = value
        report.append(f"  {group}.{key} = {value}   <- {src}")
    return out, report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=("docx", "css", "json"))
    ap.add_argument("source")
    ap.add_argument("--out", help="write tokens JSON here (default: print to stdout)")
    args = ap.parse_args()

    found = {"docx": from_docx, "css": from_css, "json": from_json}[args.kind](args.source)
    if not found:
        print("No tokens found in the source.", file=sys.stderr)
        sys.exit(1)
    tokens, report = merge(found)

    print("Inferred from source:", file=sys.stderr)
    print('\n'.join(report), file=sys.stderr)
    missing = [f"{g}.{k}" for g, k in (("colors", "ink"), ("colors", "accent"), ("colors", "muted"),
                                        ("fonts", "body"), ("fonts", "heading"))
               if (g, k) not in found]
    if missing:
        print("Not in source (defaults kept): " + ", ".join(missing), file=sys.stderr)
    c = tokens["colors"]
    for role in ("ink", "accent", "muted"):
        ratio = contrast(c[role], "#FFFFFF")
        if ratio < 4.5:
            print(f"Warning: colors.{role} {c[role]} has contrast {ratio:.1f}:1 on white (< 4.5:1).",
                  file=sys.stderr)

    text = json.dumps(tokens, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text)
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
