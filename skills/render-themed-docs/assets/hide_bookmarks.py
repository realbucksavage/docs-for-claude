"""
Renames every bookmark in a .docx, and the internal links that point at it, to
start with "_". Pandoc's docx writer turns each heading or element identifier
into a bookmark; Word treats bookmarks whose names start with "_" as hidden, so
they are not shown even with "Show bookmarks" turned on. Pandoc itself rewrites
identifiers that do not start with a letter, so this runs on its output.

Usage:
    python3 hide_bookmarks.py <file.docx>

Rewrites the file in place. Standard library only.
"""
import re
import shutil
import sys
import tempfile
import zipfile

MAX_NAME = 40  # Word's bookmark name limit

BOOKMARK = re.compile(r'(<w:bookmarkStart\b[^>]*?\bw:name=")([^"]*)(")')
ANCHOR = re.compile(r'(\bw:anchor=")([^"]*)(")')


def build_map(names):
    mapping, used = {}, set(names)
    for name in names:
        if name.startswith('_') or name in mapping:
            continue
        new = ('_' + name)[:MAX_NAME]
        n = 1
        while new in used:
            new = f"_bm{n}"
            n += 1
        mapping[name] = new
        used.add(new)
    return mapping


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: hide_bookmarks.py <file.docx>")
    path = sys.argv[1]

    with zipfile.ZipFile(path) as z:
        parts = {i.filename: z.read(i.filename) for i in z.infolist()}
        infos = z.infolist()

    xml_parts = [n for n in parts if n.startswith('word/') and n.endswith('.xml')]
    names = []
    for n in xml_parts:
        names += [m.group(2) for m in BOOKMARK.finditer(parts[n].decode('utf-8'))]
    mapping = build_map(names)
    if not mapping:
        return

    def sub(m):
        return m.group(1) + mapping.get(m.group(2), m.group(2)) + m.group(3)

    for n in xml_parts:
        text = parts[n].decode('utf-8')
        text = ANCHOR.sub(sub, BOOKMARK.sub(sub, text))
        parts[n] = text.encode('utf-8')

    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as out:
            for info in infos:
                out.writestr(info, parts[info.filename])
    shutil.move(tmp.name, path)


if __name__ == "__main__":
    main()
