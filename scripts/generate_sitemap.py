#!/usr/bin/env python3
"""Generate public/sitemap.xml dari artikel + halaman statis Nalar."""
import re
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "src" / "content" / "articles"
OUT = ROOT / "public" / "sitemap.xml"
SITE = "https://nalar-news.pages.dev"

STATIC = ["", "/metodologi", "/tentang", "/cari",
          "/kategori/politik", "/kategori/teknologi",
          "/kategori/ekonomi", "/kategori/olahraga", "/kategori/global"]

def parse_frontmatter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^(\w+):\s*[\"']?(.*?)[\"']?\s*$", line)
        if mm:
            fm[mm.group(1)] = mm.group(2)
    return fm

def main():
    urls = [(SITE + p, "") for p in STATIC]
    for md in ARTICLES_DIR.glob("*.md"):
        try:
            fm = parse_frontmatter(md.read_text(encoding="utf-8"))
            if not fm.get("title") or fm.get("sample") == "true":
                continue
            urls.append((f'{SITE}/artikel/{fm.get("slug", md.stem)}',
                         fm.get("date", "")))
        except Exception:
            continue

    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in urls:
        out.append('<url>')
        out.append(f'<loc>{escape(loc)}</loc>')
        if lastmod:
            out.append(f'<lastmod>{lastmod}</lastmod>')
        out.append('</url>')
    out.append('</urlset>')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"Sitemap: {len(urls)} URL -> {OUT}")

if __name__ == "__main__":
    main()
