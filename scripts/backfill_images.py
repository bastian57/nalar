#!/usr/bin/env python3
"""
Nalar — backfill thumbnail SEKALI JALAN.

Untuk setiap .md di src/content/articles yang BELUM punya foto asli
(photo_source kosong atau "ai"), cari foto berlisensi bebas via
Smart Image Engine lalu update frontmatter:
  thumbnail, photo_credit, photo_source.

- Idempotent: artikel yang sudah berfoto asli (wikimedia/openverse) dilewati,
  kecuali --force.
- --dry-run : tampilkan rencana tanpa menulis file.
- --limit N : batasi jumlah artikel per run.
- --force   : proses ulang SEMUA artikel (untuk upgrade ke keyword Inggris).

Cara pakai (sekali saja, dari root repo):
    pip install requests
    python3 scripts/backfill_images.py --dry-run   # cek dulu
    python3 scripts/backfill_images.py             # eksekusi
    git add -A && git commit -m "Backfill foto asli" && git push
"""

import argparse
import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smart_image import fetch_smart_image, id_to_en_keywords  # noqa: E402

log = logging.getLogger("nalar.backfill")
ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "src" / "content" / "articles"

REAL_SOURCES = ("wikipedia", "wikimedia", "openverse")


def sanitize(s, maxlen=200):
    s = str(s or "")
    s = s.replace("\r", " ").replace("\n", " ")
    s = s.replace('"', "'").replace("\\", "")
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:maxlen]


def split_md(path):
    """Kembalikan (meta_lines, body_raw) atau (None, None) bila bukan artikel."""
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$", raw)
    if not m:
        return None, None
    return m.group(1).split("\n"), m.group(2)


def get_field(meta_lines, key):
    for line in meta_lines:
        if line.startswith(key + ":"):
            v = line.split(":", 1)[1].strip()
            if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
                v = v[1:-1]
            return v
    return ""


def set_field(meta_lines, key, value):
    newline = f'{key}: "{value}"'
    for i, line in enumerate(meta_lines):
        if line.startswith(key + ":"):
            meta_lines[i] = newline
            return
    for i, line in enumerate(meta_lines):  # sisip setelah thumbnail
        if line.startswith("thumbnail:"):
            meta_lines.insert(i + 1, newline)
            return
    meta_lines.append(newline)


def main():
    ap = argparse.ArgumentParser(description="Backfill foto asli artikel lama")
    ap.add_argument("--dry-run", action="store_true",
                    help="tampilkan rencana tanpa menulis file")
    ap.add_argument("--limit", type=int, default=0,
                    help="batasi jumlah artikel (0 = semua)")
    ap.add_argument("--force", action="store_true",
                    help="proses ulang semua artikel walau sudah berfoto")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    files = sorted(ARTICLES_DIR.glob("*.md"))
    if not files:
        log.info("Tidak ada artikel di %s", ARTICLES_DIR)
        return
    done = skipped = failed = 0
    for path in files:
        if args.limit and done >= args.limit:
            break
        meta_lines, body_raw = split_md(path)
        if not meta_lines:
            log.warning("SKIP (format tidak dikenal): %s", path.name)
            skipped += 1
            continue
        if get_field(meta_lines, "photo_source") in REAL_SOURCES and not args.force:
            skipped += 1  # sudah berfoto asli
            continue
        title = get_field(meta_lines, "title")
        category = get_field(meta_lines, "category") or "umum"
        # v2: keyword Inggris via kamus ID->EN (jauh lebih relevan di Commons)
        kws = id_to_en_keywords(title, category)
        url, credit, src = fetch_smart_image(title, category, kws)
        if not url:
            log.warning("GAGAL (tidak ketemu foto): %s", path.name)
            failed += 1
            continue
        credit = sanitize(credit, 120)
        if args.dry_run:
            log.info("DRY-RUN %-40s -> %-9s | %s", path.name, src, credit)
        else:
            set_field(meta_lines, "thumbnail", url)
            set_field(meta_lines, "photo_credit", credit)
            set_field(meta_lines, "photo_source", src)
            path.write_text(
                "---\n" + "\n".join(meta_lines) + "\n---\n" + body_raw,
                encoding="utf-8",
            )
            log.info("OK      %-40s -> %-9s | %s", path.name, src, credit)
        done += 1
        time.sleep(1.5)  # sopan ke API gratis
    log.info("Selesai: %d diperbarui, %d dilewati, %d gagal.", done, skipped, failed)


if __name__ == "__main__":
    main()
