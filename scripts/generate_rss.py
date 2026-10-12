#!/usr/bin/env python3
"""Generate public/rss.xml dari artikel Nalar (RSS 2.0)."""
import re
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "src" / "content" / "articles"
OUT = ROOT / "public" / "rss.xml"
SITE = "https://nalar-8ec.pages.dev"

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
    items = []
    for md in ARTICLES_DIR.glob("*.md"):
        try:
            text = md.read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            if not fm.get("title") or fm.get("sample") == "true":
                continue
            # pubDate RFC 822
            try:
                dt = datetime.strptime(fm.get("date", ""), "%Y-%m-%d")
                pub = dt.strftime("%a, %d %b %Y 00:00:00 +0700")
            except Exception:
                pub = ""
            items.append({
                "title": fm.get("title", ""),
                "slug": fm.get("slug", md.stem),
                "excerpt": fm.get("excerpt", ""),
                "category": fm.get("category", ""),
                "pub": pub,
                "date": fm.get("date", ""),
            })
        except Exception:
            continue
    items.sort(key=lambda x: x["date"], reverse=True)
    items = items[:50]

    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0">', '<channel>',
           f'<title>{escape("Nalar — Berita Kritis & Cerdas")}</title>',
           f'<link>{SITE}</link>',
           f'<description>{escape("Portal berita kritis, independen, dan mencerdaskan.")}</description>',
           '<language>id</language>']
    for it in items:
        out.append('<item>')
        out.append(f'<title>{escape(it["title"])}</title>')
        out.append(f'<link>{SITE}/artikel/{it["slug"]}</link>')
        out.append(f'<guid>{SITE}/artikel/{it["slug"]}</guid>')
        out.append(f'<description>{escape(it["excerpt"])}</description>')
        if it["category"]:
            out.append(f'<category>{escape(it["category"])}</category>')
        if it["pub"]:
            out.append(f'<pubDate>{it["pub"]}</pubDate>')
        out.append('</item>')
    out += ['</channel>', '</rss>']

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"RSS: {len(items)} item -> {OUT}")

if __name__ == "__main__":
    main()
