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
from urllib.parse import quote, urlparse

import feedparser
import requests

from smart_image import fetch_smart_image

# ------------------------------------------------------------------ config

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "src" / "content" / "articles"
SOURCES_FILE = Path(__file__).resolve().parent / "rss_sources.json"

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
# Model utama + fallback (coba berurutan bila 429/gagal).
# "qwen/qwen3.8-27b" = model yang TERBUKTI jalan live di Phoenix (llm_narrator.py,
# dites live 2026-10-07). JANGAN pakai llama-3.3-70b-versatile (HILANG dari Groq)
# atau qwen-qwq-32b (dihapus dari katalog Groq) — keduanya bikin run gagal total.
# Bisa dioverride tanpa edit kode via secret/variabel GROQ_LLM_MODEL.
GROQ_MODELS = [os.environ.get("GROQ_LLM_MODEL", "qwen/qwen3.8-27b"),
               "openai/gpt-oss-120b"]

MAX_ARTICLES_PER_RUN = 5
MAX_PER_CATEGORY = 2
RECENCY_HOURS = 48          # hanya berita < 48 jam (lebih longgar)
SIMILARITY_THRESHOLD = 0.80  # judul mirip -> skip (0.55 terlalu agresif)
MIN_KEYWORD_OVERLAP = 2     # syarat artikel "terkait"
MAX_RELATED = 4             # maks artikel pendukung per topik

# --- Deep Dive (analisis investigatif mingguan, 1000-1200 kata)
DEEP_DIVE_MIN_SOURCES = 3   # butuh >=3 sumber berbeda untuk 1 topik
DEEP_DIVE_RECENCY_HOURS = 168  # window 7 hari (deep dive jalan mingguan)
DEEP_DIVE_MAX_RELATED = 8   # kumpulkan bahan lebih banyak
DEEP_DIVE_MAX_TOKENS = 3000

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

DEEP_DIVE_SYSTEM_PROMPT = (
    "Kamu adalah jurnalis investigasi senior Indonesia — kritis, independen, "
    "tajam, dan berani. Kamu menulis ANALISIS MENDALAM (deep dive) dalam Bahasa "
    "Indonesia: bukan sekadar melaporkan peristiwa, tapi membongkar apa yang "
    "terjadi di baliknya. JANGAN pernah menyalin kalimat dari sumber — tulis "
    "ulang sepenuhnya dengan bahasamu sendiri sebagai analis. Tetap berbasis "
    "fakta dari bahan yang diberikan; bedakan dengan jelas antara fakta, "
    "analisis, dan prediksi. Nada cerdas, berani, mencerdaskan."
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
    """Baca judul + slug artikel yang sudah ada (anti duplikat antar-run).
    Artikel dengan 'sample: true' di frontmatter diabaikan (tidak ikut dedup)."""
    existing = []  # list of (slug, title)
    if not ARTICLES_DIR.is_dir():
        return existing
    for md in ARTICLES_DIR.glob("*.md"):
        try:
            text = md.read_text(encoding="utf-8")
            m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
            if not m:
                continue
            fm = m.group(1)
            # Skip artikel contoh
            if re.search(r"^sample:\s*true\s*$", fm, re.M | re.I):
                continue
            title = ""
            tm = re.search(r"^title:\s*[\"']?(.*?)[\"']?\s*$", fm, re.M)
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


def find_related(item, all_items, max_related=MAX_RELATED):
    """Cari artikel terkait dari sumber BERBEDA tentang topik sama."""
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
        if len(related) >= max_related:
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


def pick_deep_dive_topic(items, existing):
    """Pilih 1 topik dengan liputan multi-sumber terbanyak.

    Syarat: minimal DEEP_DIVE_MIN_SOURCES artikel terkait dari sumber berbeda.
    Dipakai mode --deep-dive (mingguan).
    """
    fresh = [it for it in items if not is_duplicate(it["title"], existing)]
    log.info("%d item setelah dedup judul (deep dive)", len(fresh))
    best, best_n = None, 0
    for it in fresh:
        related = find_related(it, items, max_related=DEEP_DIVE_MAX_RELATED)
        n = len(related)
        if n >= DEEP_DIVE_MIN_SOURCES and n > best_n:
            best, best_n = it, n
    if best:
        log.info("Topik deep dive terpilih (%d sumber): %s",
                 best_n + 1, best["title"][:60])
    return best


def run_deep_dive(items, existing, args):
    """Mode --deep-dive: 1 topik terbesar -> analisis investigatif panjang."""
    topic = pick_deep_dive_topic(items, existing)
    if not topic:
        log.info("Tidak ada topik yang memenuhi syarat deep dive "
                 "(butuh >=%d sumber berbeda) — selesai.", DEEP_DIVE_MIN_SOURCES)
        return 0
    related = find_related(topic, items, max_related=DEEP_DIVE_MAX_RELATED)
    log.info("Deep dive: %s | pendukung: %d (%s)",
             topic["title"][:60], len(related),
             ", ".join(r["source"] for r in related) or "-")
    if args.dry_run:
        log.info("[dry-run] deep dive dilewati (tidak panggil Groq).")
        return 0
    try:
        text, model = groq_generate(topic, related, deep_dive=True)
        title, body, image_keywords = parse_output(text)
        if not title:
            title = topic["title"][:90]
        if len(body.split()) < 200:
            log.warning("Deep dive terlalu pendek, dibuang: %s", title[:50])
            return 0
        save_article(title, body, topic["category"], 1 + len(related), model,
                     deep_dive=True, image_keywords=image_keywords)
    except Exception as e:
        log.error("Deep dive gagal: %s", e)
        return 0
    log.info("=== Selesai: 1 deep dive ===")
    return 0

# ------------------------------------------------------------------ Groq

def groq_generate(main_item, related, deep_dive=False):
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        log.error("GROQ_API_KEY tidak diset — hentikan.")
        sys.exit(1)

    bahan = [main_item] + related
    sum_len = 600 if deep_dive else 350
    daftar = "\n".join(
        f"- [{b['source']}] {b['title']}\n  Ringkasan: {b['summary'][:sum_len]}"
        for b in bahan
    )
    if deep_dive:
        system_prompt = DEEP_DIVE_SYSTEM_PROMPT
        user_prompt = (
            "Bahan berita (kumpulkan FAKTANYA saja, jangan salin kalimatnya):\n\n"
            f"{daftar}\n\n"
            "Tugas: tulis ANALISIS MENDALAM investigatif 1000-1200 kata dalam "
            "Bahasa Indonesia dengan struktur WAJIB berikut:\n"
            "1. Latar belakang — akar masalah dan konteks historisnya\n"
            "2. Kronologi — rangkaian peristiwa kunci secara runtut\n"
            "3. Analisis multi-sudut pandang — lihat dari sisi semua pihak "
            "yang terlibat dan terdampak\n"
            "4. Data & fakta kunci — angka, nama, dan fakta terpenting "
            "(hanya dari bahan yang diberikan)\n"
            "5. Apa yang disembunyikan — motif, kepentingan, dan hal yang "
            "tidak dikatakan media mainstream\n"
            "6. Prediksi ke depan — skenario yang mungkin terjadi\n"
            "7. Kesimpulan yang mencerdaskan — apa yang harus dipahami pembaca\n\n"
            "Format output WAJIB:\n"
            "Baris pertama: JUDUL: <judul tajam, maks 90 karakter>\n"
            "Baris kedua: kosong\n"
            "Setelahnya: isi artikel dalam Markdown (pakai ## subjudul sesuai "
            "struktur di atas, **bold**, > quote). Jangan sertakan daftar sumber.\n"
            "Baris paling akhir: FOTO: <3 kata kunci BAHASA INGGRIS yang "
            "spesifik untuk mencari foto berita relevan, dipisah koma — "
            "contoh: indonesian parliament building, jakarta>"
        )
    else:
        system_prompt = SYSTEM_PROMPT
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
            "**bold**, > quote). Jangan sertakan daftar sumber.\n"
            "Baris paling akhir: FOTO: <3 kata kunci BAHASA INGGRIS yang "
            "spesifik untuk mencari foto berita relevan, dipisah koma — "
            "contoh: artificial intelligence robot, technology>"
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
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": DEEP_DIVE_MAX_TOKENS if deep_dive else 1600,
                    # reasoning model (gpt-oss): jangan habiskan token buat mikir
                    **({"reasoning_effort": "low"} if "gpt-oss" in model else {}),
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
            min_wc = 700 if deep_dive else 300
            if wc < min_wc:
                log.warning("Artikel terlalu pendek (%d kata), tetap disimpan", wc)
            return text, model
        except Exception as e:
            last_err = e
            log.warning("Groq gagal (%s): %s", model, e)
            time.sleep(2)
    raise RuntimeError(f"Semua model Groq gagal. Terakhir: {last_err}")

# ------------------------------------------------------------------ simpan

def parse_output(text):
    """Pisahkan JUDUL: ..., badan artikel, dan FOTO: (keyword Inggris)."""
    lines = text.split("\n")
    title = ""
    image_keywords = ""
    body_start = 0
    for i, ln in enumerate(lines[:4]):
        m = re.match(r"^\s*JUDUL\s*:\s*(.+?)\s*$", ln, re.I)
        if m:
            title = m.group(1).strip().strip("\"'")
            body_start = i + 1
            break
    for ln in lines[body_start:]:
        m = re.match(r"^\s*FOTO\s*:\s*(.+?)\s*$", ln, re.I)
        if m:
            image_keywords = m.group(1).strip().strip("\"'")
            break
    body = "\n".join(lines[body_start:]).strip()
    # buang baris FOTO: dari body agar tidak tampil di artikel
    body = re.sub(r"(?m)^\s*FOTO\s*:.*$", "", body).strip()
    # buang baris pembuka "# judul" duplikat bila model tetap menulisnya
    body = re.sub(r"^#\s+.*\n", "", body, count=1).lstrip()
    return title, body, image_keywords


def excerpt_of(body, n=160):
    txt = re.sub(r"[#>*`\-]", "", body)
    txt = re.sub(r"\s+", " ", txt).strip()
    return (txt[:n] + "…") if len(txt) > n else txt


def make_thumbnail_url(title, category):
    """Generate URL thumbnail via Pollinations.ai (gratis, tanpa API key).

    Prompt dibangun dari judul + kategori, di-URL-encode penuh.
    """
    kws = sorted({w for w in keywords(title) if len(w) >= 4})[:5]
    kw_str = ", ".join(kws) if kws else title[:40]
    prompt = (
        f"editorial news illustration, {category}, {kw_str}, "
        "dramatic lighting, professional journalism style, no text"
    )
    encoded = quote(prompt, safe="")
    return (
        "https://image.pollinations.ai/prompt/"
        f"{encoded}?width=800&height=450&nologo=true&model=flux"
    )


def sanitize_frontmatter_value(s, maxlen=200):
    """Bersihkan nilai untuk frontmatter YAML: buang newline, quote, dan
    karakter kontrol agar tidak bisa inject field frontmatter lain."""
    s = str(s or "")
    s = s.replace("\r", " ").replace("\n", " ")
    s = s.replace('"', "'").replace("\\", "")
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:maxlen]


def save_article(title, body, category, n_sources, model, deep_dive=False,
                 image_keywords=""):
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    title = sanitize_frontmatter_value(title, 120)
    slug = slugify(title)
    base, i = slug, 2
    while (ARTICLES_DIR / f"{slug}.md").exists():
        slug, i = f"{base}-{i}", i + 1
    date_wib = datetime.now(WIB).strftime("%Y-%m-%d")
    # Smart Image Engine: utamakan keyword Inggris dari Groq (spesifik topik),
    # fallback ke kata kunci judul bila model tidak mengembalikan FOTO:.
    en_kws = [k.strip().lower() for k in image_keywords.split(",") if k.strip()]
    if en_kws:
        img_url, img_credit, img_source = fetch_smart_image(
            title, category, set(en_kws))
    else:
        kws = {w for w in keywords(title) if len(w) >= 4}
        img_url, img_credit, img_source = fetch_smart_image(title, category, kws)
    if img_url:
        thumbnail = img_url
        photo_credit = sanitize_frontmatter_value(img_credit, 120)
        photo_source = img_source
    else:
        thumbnail = make_thumbnail_url(title, category)  # ilustrasi AI
        photo_credit = "Ilustrasi AI / Pollinations"
        photo_source = "ai"
    excerpt = sanitize_frontmatter_value(excerpt_of(body), 200)
    img_kw_fm = sanitize_frontmatter_value(image_keywords, 120)
    frontmatter = (
        "---\n"
        f'title: "{title}"\n'
        f"date: {date_wib}\n"
        f"category: {category}\n"
        f'excerpt: "{excerpt}"\n'
        f"slug: {slug}\n"
        f'thumbnail: "{thumbnail}"\n'
        f'photo_credit: "{photo_credit}"\n'
        f'photo_source: "{photo_source}"\n'
        f'image_keywords: "{img_kw_fm}"\n'
        f"sources_count: {n_sources}\n"
        f"model: {model}\n"
        "ai_generated: true\n"
        f"{'deep_dive: true\n' if deep_dive else ''}"
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
    ap.add_argument("--deep-dive", action="store_true",
                    help="mode deep dive: 1 analisis investigatif panjang "
                         "(1000-1200 kata) dari topik multi-sumber terbesar")
    args = ap.parse_args()
    globals()["MAX_ARTICLES_PER_RUN"] = args.max
    if args.deep_dive:
        globals()["RECENCY_HOURS"] = DEEP_DIVE_RECENCY_HOURS

    log.info("=== Nalar pipeline mulai (%s)%s ===",
             datetime.now(WIB).strftime("%Y-%m-%d %H:%M WIB"),
             " [MODE DEEP DIVE]" if args.deep_dive else "")
    sources = load_sources()
    items = collect_items(sources)
    if not items:
        log.warning("Tidak ada item RSS segar — selesai tanpa artikel.")
        return 0

    existing = load_existing()
    log.info("%d artikel sudah ada di repo", len(existing))

    if args.deep_dive:
        return run_deep_dive(items, existing, args)

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
            title, body, image_keywords = parse_output(text)
            if not title:
                title = it["title"][:90]
            if len(body.split()) < 80:
                log.warning("Body terlalu pendek, lewati: %s", title[:50])
                continue
            save_article(title, body, it["category"], 1 + len(related), model,
                         image_keywords=image_keywords)
            made += 1
        except Exception as e:
            log.error("Gagal proses topik '%s': %s", it["title"][:50], e)
        time.sleep(3)  # jaga rate limit Groq free tier

    log.info("=== Selesai: %d artikel baru ===", made)

    # Generate RSS + sitemap (selalu, walau 0 artikel baru)
    for gen in ("generate_rss.py", "generate_sitemap.py"):
        try:
            import subprocess
            r = subprocess.run(
                [sys.executable, str(Path(__file__).parent / gen)],
                capture_output=True, text=True, timeout=60)
            log.info("%s: %s", gen, r.stdout.strip() or "OK")
        except Exception as e:
            log.warning("%s gagal: %s", gen, e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
