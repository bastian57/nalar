#!/usr/bin/env python3
"""
Fix manual thumbnail 2 artikel yang hasilnya ngaco di v2.
Dijalankan sekali dari root repo ~/nalar, lalu git push.

- prabowo-gandeng-mesir-... -> foto resmi Prabowo 2024 (Wikipedia)
- satpol-pp-...              -> lambang Satpol PP resmi (Wikipedia)
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "src" / "content" / "articles"

FIXES = {
    # slug prefix -> (thumbnail_url, photo_credit, photo_source)
    "prabowo-gandeng-mesir": (
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/55/"
        "Prabowo_Subianto_2024_official_portrait.jpg/800px-"
        "Prabowo_Subianto_2024_official_portrait.jpg",
        "Wikipedia / Prabowo Subianto",
        "wikipedia",
    ),
    "satpol-pp-dibentur": (
        "https://upload.wikimedia.org/wikipedia/commons/3/34/"
        "Lambang_SAT_POL_PP.png",
        "Wikipedia / Polisi Pamong Praja",
        "wikipedia",
    ),
}


def set_field(lines, key, value):
    nl = f'{key}: "{value}"'
    for i, ln in enumerate(lines):
        if ln.startswith(key + ":"):
            lines[i] = nl
            return


def main():
    done = 0
    for path in sorted(ARTICLES_DIR.glob("*.md")):
        for prefix, (url, credit, src) in FIXES.items():
            if path.name.startswith(prefix):
                raw = path.read_text(encoding="utf-8")
                m = re.match(r"^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$", raw)
                if not m:
                    print("SKIP (format):", path.name)
                    continue
                lines, body = m.group(1).split("\n"), m.group(2)
                set_field(lines, "thumbnail", url)
                set_field(lines, "photo_credit", credit)
                set_field(lines, "photo_source", src)
                path.write_text("---\n" + "\n".join(lines) + "\n---\n" + body,
                                encoding="utf-8")
                print("FIXED:", path.name, "->", credit)
                done += 1
    print(f"Selesai: {done} artikel diperbaiki.")


if __name__ == "__main__":
    main()
