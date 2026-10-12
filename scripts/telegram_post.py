#!/usr/bin/env python3
"""
Nalar — Telegram autoposter.
Kirim artikel baru ke channel Telegram via Bot API.
Dijalankan setelah generate_news.py di GitHub Actions.

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "src" / "content" / "articles"
SITE = "https://nalar-news.pages.dev"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("nalar-tg")


def get_new_articles():
    """Ambil daftar file .md baru dari git (staged atau commit terakhir)."""
    try:
        # Coba dari git diff (untuk workflow yang commit dulu)
        r = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD", "--",
             "src/content/articles/"],
            capture_output=True, text=True, cwd=ROOT, timeout=30)
        files = [f.strip() for f in r.stdout.splitlines() if f.strip().endswith(".md")]
        if files:
            return files
    except Exception as e:
        log.warning("git diff gagal: %s", e)
    # Fallback: semua artikel (untuk test manual)
    return []


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


def send_photo(token, chat_id, photo_url, caption):
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    # Telegram caption max 1024 char
    if len(caption) > 1000:
        caption = caption[:997] + "..."
    r = requests.post(url, data={
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML",
    }, timeout=30)
    return r


def send_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    if len(text) > 4000:
        text = text[:3997] + "..."
    r = requests.post(url, data={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }, timeout=30)
    return r


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diset.")
        return 1

    files = get_new_articles()
    if not files:
        log.info("Tidak ada artikel baru — skip.")
        return 0

    log.info("%d artikel baru untuk di-post", len(files))
    sent = 0
    for f in files:
        p = ROOT / f
        if not p.exists():
            continue
        try:
            fm = parse_frontmatter(p.read_text(encoding="utf-8"))
            title = fm.get("title", "Artikel Baru")
            excerpt = fm.get("excerpt", "")
            slug = fm.get("slug", p.stem)
            category = fm.get("category", "").upper()
            thumbnail = fm.get("thumbnail", "")
            link = f"{SITE}/artikel/{slug}"

            # Escape HTML untuk Telegram
            def esc(s):
                return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            caption = f"🧠 <b>{esc(title)}</b>\n\n{esc(excerpt)}\n\n🔗 <a href=\"{link}\">Baca selengkapnya di Nalar</a>"
            if category:
                caption = f"[{category}] " + caption

            if thumbnail and thumbnail.startswith("http"):
                r = send_photo(token, chat_id, thumbnail, caption)
            else:
                r = send_message(token, chat_id, caption)

            if r.status_code == 200:
                log.info("Terkirim: %s", title[:50])
                sent += 1
            else:
                log.warning("Gagal kirim %s: %s %s", title[:40], r.status_code,
                            r.text[:200])
        except Exception as e:
            log.error("Error proses %s: %s", f, e)
        time.sleep(2)  # hindari rate limit

    log.info("Selesai: %d/%d terkirim", sent, len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
