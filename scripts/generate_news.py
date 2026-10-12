#!/usr/bin/env python3
"""
Nalar — content pipeline otonom.

Alur: RSS multi-sumber -> pilih topik terhangat -> kumpulkan artikel terkait
-> Groq AI tulis ulang (kritis-analitis, sudut pandang sendiri)
-> simpan markdown + frontmatter ke src/content/articles/

Dijalankan oleh GitHub Actions tiap 6 jam. API key HANYA via env GROQ_API_KEY.
"""

import argparse
import difflib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests

# ------------------------------------------------------------------ config

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "src" / "content" / "articles"
SOURCES_FILE = Path(__file__).resolve().parent / "rss_sources.json"

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
# Model utama + fallback (coba berurutan bila 429/gagal)
GROQ_MODELS = ["llama-3.3-70b-versatile", "qwen-qwq-32b"]

MAX_ARTICLES_PER_RUN = 5
MAX_PER_CATEGORY = 2
RECENCY_HOURS = 36          # hanya berita < 36 jam
SIMILARITY_THRESHOLD = 0.55  # judul mirip -> skip (anti duplikat)
MIN_KEYWORD_OVERLAP = 2     # syarat artikel "terkait"
MAX_RELATED = 4             # maks artikel pendukung per topik

WIB = timezone(timedelta(hours=7))

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    )
}

STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "pada", "adalah",
    "ini", "itu", "dalam", "sebagai", "oleh", "akan", "telah", "sudah",
    "juga", "tidak", "ada", "atau", "tapi", "namun", "karena", "saat",
    "setelah", "sebelum", "antara", "lebih", "sangat", "para", "sebuah",
    "seorang", "mereka", "kita", "kami", "saya", "dia", "nya", "the",
    "jadi", "agar", "bisa", "dapat", "harus", "kembali", "baru", "kini",
    "usai", "soal", "terkait", "hingga", "tanpa", "bagi", "serta",
}

SYSTEM_PROMPT = (
    "Kamu adalah jurnalis investigasi senior Indonesia yang kritis, independen, "
    "dan tajam. Tulis artikel berita ORIGINAL dalam Bahasa Indonesia dengan gaya "
    "kritis-analitis seperti jurnalis investigasi. JANGAN pernah menyalin kalimat "
    "dari sumber — tulis ulang sepenuhnya dengan bahasamu sendiri, dari sudut "
    "pandangmu sebagai analis. Wajib ada: (1) konteks 'Mengapa ini penting', "
    "(2) bagian 'Apa yang tidak dikatakan media mainstream' — gali motif, "
    "kepentingan, dan hal yang disembunyikan di balik peristiwa. "
    "Panjang 400-500 kata. Struktur: judul tajam, lead satu paragraf, isi, "
    "analisis kritis, penutup yang mencerdaskan. Nada cerdas, berani, tidak "
    "netral-netral saja, tapi tetap berbasis fakta dari bahan yang diberikan."
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("nalar")

# ------------------------------------------------------------------ helpers

def load_sources():
    with open(SOURCES_FILE, encoding="utf-8") as f:
        return json.load(f)


def entry_datetime(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def clean_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()


def keywords(title):
    words = re.findall(r"[a-zA-Z]{4,}", title.lower())
    return {w for w in words if w not in STOPWORDS}


def slugify(title, maxlen=60):
    s = title.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s[:maxlen].strip("-") or "artikel"


def fetch_feed(url):
    """Ambil satu RSS feed. Gagal -> [] (tidak menggagalkan run)."""
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
        if not feed.entries:
            log.warning("Feed kosong/rusak: %s", url)
            return []
        log.info("OK %-42s %d item", urlparse(url).netloc, len(feed.entries))
        return feed.entries
    except Exception as e:
        log.warning("Gagal fetch %s: %s", url, e)
        return []


def collect_items(sources):
    """Kumpulkan semua item dari semua feed, filter recency."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENCY_HOURS)
    items = []
    for category, feeds in sources.items():
        if category.startswith("_"):
            continue
        for feed in feeds:
            for e in fetch_feed(feed["url"]):
                title = (e.get("title") or "").strip()
                if not title:
                    continue
                dt = entry_datetime(e)
                if dt < cutoff:
                    continue
                items.append({
                    "title": title,
                    "link": (e.get("link") or "").strip(),
                    "summary": clean_html(
                        e.get("summary") or e.get("description") or ""
                    )[:600],
                    "source": feed["name"],
                    "category": category,
                    "published": dt,
                    "keywords": keywords(title),
                })
    log.info("Terkumpul %d item segar (<%dh)", len(items), RECENCY_HOURS)
    return items

# ------------------------------------------------------- dedup & related

def load_existing():
    """Baca judul + slug artikel yang sudah ada (anti duplikat antar-run)."""
    existing = []  # list of (slug, title)
    if not ARTICLES_DIR.is_dir():
        return existing
    for md in ARTICLES_DIR.glob("*.md"):
        try:
            text = md.read_text(encoding="utf-8")
            m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
            title = ""
            if m:
                tm = re.search(r"^title:\s*[\"']?(.*?)[\"']?\s*$",
                               m.group(1), re.M)
                if tm:
                    title = tm.group(1).strip()
            existing.append((md.stem, title or md.stem))
        except Exception:
            continue
    return existing


def is_duplicate(title, existing):
    norm = title.lower().strip()
    for slug, old_title in existing:
        if slugify(title) == slug:
            return True
        if old_title and difflib.SequenceMatcher(
            None, norm, old_title.lower().strip()
        ).ratio() >= SIMILARITY_THRESHOLD:
            return True
    return False


def find_related(item, all_items):
    """Cari 3-5 artikel terkait dari sumber BERBEDA tentang topik sama."""
    cands = []
    for other in all_items:
        if other is item or other["source"] == item["source"]:
            continue
        overlap = len(item["keywords"] & other["keywords"])
        if overlap >= MIN_KEYWORD_OVERLAP:
            cands.append((overlap, other["published"], other))
    cands.sort(key=lambda x: (-x[0], -x[1].timestamp()))  # overlap terbesar, terbaru
    seen_sources = set()
    related = []
    for _, _, o in cands:
        if o["source"] in seen_sources:
            continue
        seen_sources.add(o["source"])
        related.append(o)
        if len(related) >= MAX_RELATED:
            break
    return related


def pick_topics(items, existing):
    """Pilih 3-5 topik terhangat, diversifikasi kategori, skip duplikat."""
    fresh = [it for it in items if not is_duplicate(it["title"], existing)]
    log.info("%d item setelah dedup judul", len(fresh))
    fresh.sort(key=lambda x: x["published"], reverse=True)
    picked, per_cat = [], {}
    for it in fresh:
        if per_cat.get(it["category"], 0) >= MAX_PER_CATEGORY:
            continue
        picked.append(it)
        per_cat[it["category"]] = per_cat.get(it["category"], 0) + 1
        if len(picked) >= MAX_ARTICLES_PER_RUN:
            break
    log.info("Terpilih %d topik: %s",
             len(picked), [p["title"][:45] for p in picked])
    return picked

# ------------------------------------------------------------------ Groq

def groq_generate(main_item, related):
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        log.error("GROQ_API_KEY tidak diset — hentikan.")
        sys.exit(1)

    bahan = [main_item] + related
    daftar = "\n".join(
        f"- [{b['source']}] {b['title']}\n  Ringkasan: {b['summary'][:350]}"
        for b in bahan
    )
    user_prompt = (
        "Bahan berita (kumpulkan FAKTANYA saja, jangan salin kalimatnya):\n\n"
        f"{daftar}\n\n"
        "Tugas: tulis artikel berita original dalam Bahasa Indonesia, gaya "
        "kritis-analitis seperti jurnalis investigasi. JANGAN copy kalimat dari "
        "sumber. Tambahkan konteks 'mengapa ini penting' dan 'apa yang tidak "
        "dikatakan media mainstream'. 400-500 kata.\n\n"
        "Format output WAJIB:\n"
        "Baris pertama: JUDUL: <judul tajam, maks 90 karakter>\n"
        "Baris kedua: kosong\n"
        "Setelahnya: isi artikel dalam Markdown (boleh pakai ## subjudul, "
        "**bold**, > quote). Jangan sertakan daftar sumber."
    )

    last_err = None
    for model in GROQ_MODELS:
        try:
            log.info("Groq: model %s ...", model)
            r = requests.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1600,
                },
                timeout=120,
            )
            if r.status_code == 429:
                log.warning("Rate limit pada %s, coba model berikut", model)
                time.sleep(5)
                continue
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            wc = len(text.split())
            log.info("Groq OK (%s): %d kata", model, wc)
            if wc < 300:
                log.warning("Artikel terlalu pendek (%d kata), tetap disimpan", wc)
            return text, model
        except Exception as e:
            last_err = e
            log.warning("Groq gagal (%s): %s", model, e)
            time.sleep(2)
    raise RuntimeError(f"Semua model Groq gagal. Terakhir: {last_err}")

# ------------------------------------------------------------------ simpan

def parse_output(text):
    """Pisahkan JUDUL: ... dari badan artikel."""
    lines = text.split("\n")
    title = ""
    body_start = 0
    for i, ln in enumerate(lines[:4]):
        m = re.match(r"^\s*JUDUL\s*:\s*(.+?)\s*$", ln, re.I)
        if m:
            title = m.group(1).strip().strip("\"'")
            body_start = i + 1
            break
    body = "\n".join(lines[body_start:]).strip()
    # buang baris pembuka "# judul" duplikat bila model tetap menulisnya
    body = re.sub(r"^#\s+.*\n", "", body, count=1).lstrip()
    return title, body


def excerpt_of(body, n=160):
    txt = re.sub(r"[#>*`\-]", "", body)
    txt = re.sub(r"\s+", " ", txt).strip()
    return (txt[:n] + "…") if len(txt) > n else txt


def save_article(title, body, category, n_sources, model):
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(title)
    base, i = slug, 2
    while (ARTICLES_DIR / f"{slug}.md").exists():
        slug, i = f"{base}-{i}", i + 1
    date_wib = datetime.now(WIB).strftime("%Y-%m-%d")
    frontmatter = (
        "---\n"
        f'title: "{title}"\n'
        f"date: {date_wib}\n"
        f"category: {category}\n"
        f'excerpt: "{excerpt_of(body)}"\n'
        f"slug: {slug}\n"
        f"sources_count: {n_sources}\n"
        f"model: {model}\n"
        "ai_generated: true\n"
        "---\n"
    )
    (ARTICLES_DIR / f"{slug}.md").write_text(
        frontmatter + "\n" + body.strip() + "\n", encoding="utf-8")
    log.info("Disimpan: src/content/articles/%s.md", slug)
    return slug

# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description="Nalar news pipeline")
    ap.add_argument("--dry-run", action="store_true",
                    help="coba RSS + dedup tanpa panggil Groq/menyimpan")
    ap.add_argument("--max", type=int, default=MAX_ARTICLES_PER_RUN)
    args = ap.parse_args()
    globals()["MAX_ARTICLES_PER_RUN"] = args.max

    log.info("=== Nalar pipeline mulai (%s) ===",
             datetime.now(WIB).strftime("%Y-%m-%d %H:%M WIB"))
    sources = load_sources()
    items = collect_items(sources)
    if not items:
        log.warning("Tidak ada item RSS segar — selesai tanpa artikel.")
        return 0

    existing = load_existing()
    log.info("%d artikel sudah ada di repo", len(existing))
    topics = pick_topics(items, existing)
    if not topics:
        log.info("Tidak ada topik baru — selesai.")
        return 0

    made = 0
    for it in topics:
        related = find_related(it, items)
        log.info("Topik: %s | pendukung: %d (%s)",
                 it["title"][:60], len(related),
                 ", ".join(r["source"] for r in related) or "-")
        if args.dry_run:
            continue
        try:
            text, model = groq_generate(it, related)
            title, body = parse_output(text)
            if not title:
                title = it["title"][:90]
            if len(body.split()) < 80:
                log.warning("Body terlalu pendek, lewati: %s", title[:50])
                continue
            save_article(title, body, it["category"], 1 + len(related), model)
            made += 1
        except Exception as e:
            log.error("Gagal proses topik '%s': %s", it["title"][:50], e)
        time.sleep(3)  # jaga rate limit Groq free tier

    log.info("=== Selesai: %d artikel baru ===", made)
    return 0


if __name__ == "__main__":
    sys.exit(main())
