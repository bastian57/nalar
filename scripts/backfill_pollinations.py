#!/usr/bin/env python3
"""
Nalar — Backfill thumbnail ilustrasi AI (v5.4).

Artikel lama yang thumbnail-nya masih foto stok generik diganti ke ilustrasi
AI Pollinations (prompt dari judul + image_desc yang tersimpan di frontmatter).
Jalankan lewat workflow backfill-images.yml (tombol Run workflow, manual)
atau lokal:  python scripts/backfill_pollinations.py --limit 30

Opsi:
  --limit N    proses maks N artikel per jalan (default 30; runtime ~30-60 dtk
               per artikel karena warming Pollinations)
  --all        proses juga artikel yang sudah berlabel AI (refresh prompt baru)
  --no-warm    tulis URL tanpa warming (cepat, tapi tidak memverifikasi
               Pollinations hidup)
  --dry-run    hanya tampilkan rencana, tanpa mengubah file

Hanya field thumbnail/photo_credit/photo_source di frontmatter yang diubah;
isi artikel tidak disentuh.
"""
import argparse
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_image import (AI_CREDIT, build_illustration_prompt, pollinations_url,
                      warm_pollinations)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("nalar-backfill")

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "src" / "content" / "articles"

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def parse_frontmatter(text):
    m = _FM_RE.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^(\w+):\s*[\"']?(.*?)[\"']?\s*$", line)
        if mm:
            fm[mm.group(1)] = mm.group(2)
    return fm


def set_fm_field(text, key, value):
    """Ganti nilai field frontmatter (atau sisipkan bila belum ada)."""
    pat = re.compile(rf"^({key}:\s*)[\"']?.*?[\"']?\s*$", re.M)

    def repl(m):
        return f'{m.group(1)}"{value}"'

    if pat.search(text):
        return pat.sub(repl, text, count=1)
    # Sisipkan sebelum penutup frontmatter
    return _FM_RE.sub(
        lambda m: m.group(0).replace("\n---", f'\n{key}: "{value}"\n---', 1),
        text, count=1)


def main():
    ap = argparse.ArgumentParser(description="Backfill thumbnail ilustrasi AI")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--all", action="store_true",
                    help="proses juga artikel yang sudah berlabel AI")
    ap.add_argument("--no-warm", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = sorted(ARTICLES_DIR.glob("*.md"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    done = skipped = failed = 0
    for p in files:
        if done >= args.limit:
            break
        text = p.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if not fm.get("slug") or not fm.get("title"):
            skipped += 1
            continue
        if fm.get("photo_source") == "ai" and not args.all:
            skipped += 1
            continue
        prompt = build_illustration_prompt(
            fm.get("title", ""), fm.get("category", ""),
            fm.get("image_desc", ""), fm.get("excerpt", ""))
        url = pollinations_url(prompt, fm["slug"])
        if args.dry_run:
            log.info("[dry-run] %s -> %s", fm["slug"], url[:90])
            done += 1
            continue
        if not args.no_warm and not warm_pollinations(url):
            log.warning("Pollinations gagal untuk %s — lewati (stok dipertahankan)",
                        fm["slug"])
            failed += 1
            continue
        text = set_fm_field(text, "thumbnail", url)
        text = set_fm_field(text, "photo_credit", AI_CREDIT)
        text = set_fm_field(text, "photo_source", "ai")
        p.write_text(text, encoding="utf-8")
        log.info("Updated: %s", fm["slug"])
        done += 1

    log.info("Selesai: %d diperbarui, %d dilewati, %d gagal", done, skipped, failed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
