#!/usr/bin/env python3
"""
Nalar — content pipeline otonom v5.

1 artikel/jam, rotasi 6 kategori: politik, ekonomi, isu global, teknologi,
sejarah, konspirasi/misteri.
- Breaking (politik/ekonomi/global/teknologi): RSS multi-sumber.
- Sejarah: Wikipedia "on this day" + archive.org (evergreen).
- Konspirasi: PullPush (Reddit) + antrean evergreen archive.org.
-> Groq AI tulis ulang (kritis-analitis, sudut pandang sendiri)
-> simpan markdown + frontmatter ke src/content/articles/

Dijalankan oleh GitHub Actions tiap jam. API key HANYA via env GROQ_API_KEY.
Budget Groq free tier: single-pass generation per artikel (200K TPD).
"""

import argparse
import difflib
import hashlib
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

try:
    from archive_engine import search_archive
except Exception:  # archive_engine opsional — pipeline tetap jalan tanpanya
    search_archive = None

# ------------------------------------------------------------------ config

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "src" / "content" / "articles"
SOURCES_FILE = Path(__file__).resolve().parent / "rss_sources.json"

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
# Model utama + fallback (coba berurutan bila 429/gagal).
# v5: "openai/gpt-oss-120b" primer. CATATAN: "qwen/qwen3-32b" PENSIUN dari
# katalog Groq 2026-07-17 (404), dan "qwen/qwen3.8-27b" statusnya preview-only —
# JANGAN jadikan primer. JANGAN pakai llama-3.3-70b-versatile (HILANG dari
# Groq) atau qwen-qwq-32b (dihapus dari katalog Groq) — keduanya bikin run
# gagal total. Bisa dioverride tanpa edit kode via secret/variabel GROQ_LLM_MODEL.
GROQ_MODELS = [os.environ.get("GROQ_LLM_MODEL", "openai/gpt-oss-120b"),
               "openai/gpt-oss-20b"]

MAX_ARTICLES_PER_RUN = 1    # v5: 1 artikel per run (cron jalan tiap jam)
MAX_PER_CATEGORY = 2
RECENCY_HOURS = 48          # hanya berita < 48 jam (lebih longgar)
SIMILARITY_THRESHOLD = 0.80  # judul mirip -> skip (0.55 terlalu agresif)
SIMHASH_HAMMING_MAX = 16    # SimHash 64-bit: beda <=16 bit = near-duplicate
                            # (judul berita pendek: parafrase tipikal berjarak 12-13,
                            # topik beda berjarak ~32)
MIN_KEYWORD_OVERLAP = 2     # syarat artikel "terkait"
MAX_RELATED = 4             # maks artikel pendukung per topik

# --- v5: rotasi kategori per jam (jam WIB mod 6) -> 4 slot/kategori/hari
CATEGORY_ROTATION = [
    "politik", "ekonomi", "global", "teknologi", "sejarah", "konspirasi",
]
BREAKING_CATEGORIES = {"politik", "ekonomi", "global", "teknologi"}

# --- v5: state antar-run (git sebagai database) + antrean evergreen
STATE_FILE = Path(__file__).resolve().parent / "state.json"
EVERGREEN_FILE = Path(__file__).resolve().parent / "evergreen_queue.json"

# --- v5: sumber konspirasi/misteri (PullPush = arsip Reddit, tanpa auth)
PULLPUSH_SUBS = ["conspiracy", "HighStrangeness", "UnresolvedMysteries", "UFOs"]
PULLPUSH_API = "https://api.pullpush.io/reddit/search/submission/"

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

# --- v5: prompt kategori sejarah & konspirasi
SEJARAH_SYSTEM_PROMPT = (
    "Kamu adalah sejarawan populer Indonesia yang kritis dan cerdas — menulis "
    "dalam Bahasa Indonesia dengan gaya naratif yang hidup, bukan gaya buku "
    "teks membosankan. Tugasmu: menghidupkan kembali peristiwa sejarah agar "
    "pembaca MERASA ada di sana, lalu menjelaskan mengapa peristiwa itu masih "
    "relevan hari ini. JANGAN menyalin kalimat dari bahan — tulis ulang dengan "
    "bahasamu sendiri. Bedakan fakta sejarah yang terdokumentasi dari tafsir "
    "atau legenda; kalau sesuatu masih diperdebatkan sejarawan, katakan "
    "terus terang. Panjang 400-500 kata. Struktur: judul tajam, lead yang "
    "memikat, kronologi/narasi peristiwa, konteks 'mengapa ini penting', "
    "dan penutup yang mencerdaskan."
)

KONSPIRASI_SYSTEM_PROMPT = (
    "Kamu adalah pembedah misteri Indonesia yang kritis, skeptis tapi terbuka "
    "— menulis dalam Bahasa Indonesia. Tugasmu: mengambil sebuah klaim misteri/"
    "konspirasi, lalu MEMBEDAHNYA dengan pisau analisis: (1) apa klaimnya, "
    "(2) bukti apa yang diajukan pendukungnya, (3) apa kata penjelasan "
    "ilmiah/skeptis, (4) beri label tiap klaim kunci: [TERBUKTI] / "
    "[BELUM TERBUKTI] / [TIDAK TERVERIFIKASI]. DILARANG menuduh orang/lembaga "
    "tanpa bukti; DILARANG menyajikan teori sebagai fakta; DILARANG pakai "
    "'katanya' tanpa atribusi jelas ('menurut ...'). JANGAN menyalin kalimat "
    "dari bahan — tulis ulang dengan bahasamu sendiri. Panjang 400-500 kata. "
    "Struktur: judul tajam, misterinya apa, bedah bukti per klaim, penjelasan "
    "alternatif yang masuk akal, dan kesimpulan kritis yang mencerdaskan."
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


def collect_items(sources, only_category=None):
    """Kumpulkan semua item dari semua feed, filter recency.
    v5: only_category -> hanya kumpulkan 1 kategori (run per jam)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENCY_HOURS)
    items = []
    for category, feeds in sources.items():
        if category.startswith("_"):
            continue
        if only_category and category != only_category:
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
    log.info("Terkumpul %d item segar (<%dh)%s", len(items), RECENCY_HOURS,
             f" kategori {only_category}" if only_category else "")
    return items

# ------------------------------------------------------- v5: state & SimHash

def load_state():
    """Muat state antar-run (seen URLs/hashes, topik yang sudah dipakai)."""
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    """Simpan state; batasi ukuran list agar file tidak membengkak."""
    try:
        for k in ("seen_urls", "seen_hashes", "used_evergreen"):
            if isinstance(state.get(k), list) and len(state[k]) > 3000:
                state[k] = state[k][-3000:]
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
    except Exception as e:
        log.warning("Gagal simpan state: %s", e)


def simhash(text, bits=64):
    """SimHash sederhana (md5 = stabil antar-run) untuk dedup near-duplicate."""
    v = [0] * bits
    words = set(re.findall(r"[a-z]{3,}", (text or "").lower()))
    for w in words:
        h = int(hashlib.md5(w.encode()).hexdigest(), 16) & ((1 << bits) - 1)
        for i in range(bits):
            v[i] += 1 if (h >> i) & 1 else -1
    fp = 0
    for i in range(bits):
        if v[i] > 0:
            fp |= (1 << i)
    return fp


def hamming(a, b):
    return bin(a ^ b).count("1")


def is_near_duplicate(title, existing_hashes):
    """True bila judul mirip dengan artikel yang sudah ada (SimHash)."""
    h = simhash(title)
    return any(hamming(h, eh) <= SIMHASH_HAMMING_MAX for eh in existing_hashes)


# ------------------------------------------------- v5: sumber non-RSS

def pop_evergreen(category, state):
    """Ambil 1 topik evergreen yang belum dipakai untuk kategori.
    Jaminan 1 artikel/jam walau sumber breaking sedang sepi."""
    try:
        with open(EVERGREEN_FILE, encoding="utf-8") as f:
            bank = json.load(f)
    except Exception as e:
        log.warning("Evergreen bank tidak bisa dibaca: %s", e)
        return None
    used = set(state.get("used_evergreen", []))
    for i, item in enumerate(bank.get(category, [])):
        key = f"{category}:{i}:{(item.get('topic') or '')[:40]}"
        if key not in used:
            used.add(key)
            state["used_evergreen"] = sorted(used)
            log.info("Evergreen: %s", item.get("topic", "")[:60])
            return item
    log.warning("Bank evergreen '%s' habis — semua topik sudah dipakai.", category)
    return None


def archive_enrichment(query, rows=3):
    """Perkaya bahan dengan deskripsi item archive.org (ringan, 1 HTTP call).
    Gagal -> string kosong (tidak menggagalkan run)."""
    if not search_archive or not query:
        return ""
    try:
        hits = search_archive(query, rows=rows)
        parts = []
        for h in hits:
            desc = (h.get("description") or "")[:400]
            if desc:
                parts.append(f"- [{h.get('title','?')[:60]}] {desc}")
        return "\n".join(parts)
    except Exception as e:
        log.warning("Archive enrichment gagal: %s", e)
        return ""


def fetch_onthisday(state):
    """Ambil 1 peristiwa 'hari ini dalam sejarah' dari Wikipedia
    (id.wikipedia -> fallback en.wikipedia)."""
    today = datetime.now(WIB)
    mm, dd = f"{today.month:02d}", f"{today.day:02d}"
    for lang in ("id", "en"):
        try:
            url = (f"https://{lang}.wikipedia.org/api/rest_v1/"
                   f"feed/onthisday/events/{mm}/{dd}")
            r = requests.get(url, headers=UA, timeout=20)
            r.raise_for_status()
            events = r.json().get("events", [])
            used = set(state.get("used_onthisday", []))
            for ev in events:
                year = ev.get("year")
                txt = (ev.get("text") or "").strip()
                if not txt or not year:
                    continue
                key = f"{year}:{(txt)[:60]}"
                if key in used:
                    continue
                used.add(key)
                state["used_onthisday"] = sorted(used)[-500:]
                log.info("On-this-day (%s): %s — %s", lang, year,
                         txt[:60])
                return {"year": year, "text": txt, "lang": lang}
        except Exception as e:
            log.warning("onthisday %s gagal: %s", lang, e)
    return None


def fetch_pullpush(state, days=7):
    """Ambil 1 thread misteri/konspirasi terpanas dari PullPush.io
    (arsip Reddit, tanpa auth). 429 -> backoff 1x per subreddit."""
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    used = set(state.get("used_pullpush", []))
    for sub in PULLPUSH_SUBS:
        data = None
        for attempt in range(2):
            try:
                r = requests.get(
                    PULLPUSH_API,
                    params={"subreddit": sub, "after": since, "size": 20,
                            "sort": "desc", "sort_type": "score"},
                    headers=UA, timeout=25)
                if r.status_code == 429 and attempt == 0:
                    log.warning("PullPush r/%s 429 — backoff 20 dtk", sub)
                    time.sleep(20)
                    continue
                r.raise_for_status()
                data = r.json().get("data", [])
                break
            except Exception as e:
                log.warning("PullPush r/%s gagal: %s", sub, e)
                break
        if not data:
            continue
        for p in data:
            pid = p.get("id")
            title = (p.get("title") or "").strip()
            if not pid or pid in used or len(title.split()) < 4:
                continue
            used.add(pid)
            state["used_pullpush"] = sorted(used)[-500:]
            log.info("PullPush r/%s: %s", sub, title[:60])
            return {"id": pid, "title": title,
                    "selftext": (p.get("selftext") or "")[:800],
                    "subreddit": sub, "score": p.get("score", 0)}
    return None

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
        title, body, image_keywords, image_desc = parse_output(text)
        if not title:
            title = topic["title"][:90]
        if len(body.split()) < 200:
            log.warning("Deep dive terlalu pendek, dibuang: %s", title[:50])
            return 0
        save_article(title, body, topic["category"], 1 + len(related), model,
                     deep_dive=True, image_keywords=image_keywords,
                     image_desc=image_desc)
    except Exception as e:
        log.error("Deep dive gagal: %s", e)
        return 0
    log.info("=== Selesai: 1 deep dive ===")
    return 0

# ------------------------------------------------------- v5: alur per jam

OUTPUT_FORMAT_TAIL = (
    "\n\nFormat output WAJIB:\n"
    "Baris pertama: JUDUL: <judul tajam, maks 90 karakter>\n"
    "Baris kedua: kosong\n"
    "Setelahnya: isi artikel dalam Markdown (boleh pakai ## subjudul, "
    "**bold**, > quote). Jangan sertakan daftar sumber.\n"
    "Baris paling akhir: FOTO: <3 kata kunci BAHASA INGGRIS yang spesifik "
    "untuk mencari foto berita relevan, dipisah koma>\n"
    "Baris SEBELUM TERAKHIR (sebelum FOTO): GAMBAR: <deskripsi visual detail "
    "dalam BAHASA INGGRIS, 1-2 kalimat, untuk AI image generator — gambarkan "
    "scene foto jurnalistik yang paling mewakili isi artikel.>"
)


def write_article(user_prompt, category, n_sources, system_prompt,
                  existing, existing_hashes, state, args, min_wc=300):
    """Satu alur tulis: Groq -> parse -> dedup judul -> simpan. Return 1/0."""
    if args.dry_run:
        log.info("[dry-run] tulis artikel %s dilewati.", category)
        return 0
    try:
        text, model = groq_call(system_prompt, user_prompt, min_wc=min_wc)
        title, body, image_keywords, image_desc = parse_output(text)
        if not title or len(body.split()) < 80:
            log.warning("Output Groq tidak layak, dibuang.")
            return 0
        if is_duplicate(title, existing):
            log.warning("Judul duplikat (difflib), dibuang: %s", title[:50])
            return 0
        if is_near_duplicate(title, existing_hashes):
            log.warning("Judul near-duplikat (simhash), dibuang: %s", title[:50])
            return 0
        save_article(title, body, category, n_sources, model,
                     image_keywords=image_keywords, image_desc=image_desc)
        h = simhash(title)
        existing.append((slugify(title), title))
        existing_hashes.append(h)
        state.setdefault("seen_hashes", []).append(str(h))
        return 1
    except Exception as e:
        log.error("Gagal tulis artikel %s: %s", category, e)
        return 0


def run_breaking(category, sources, existing, existing_hashes, state, args):
    """Breaking news: RSS 1 kategori -> 1 topik terbaru -> sintesis multi-sumber.
    Sepi berita -> fallback evergreen (sejarah/konspirasi) agar 1/jam terjaga."""
    items = collect_items(sources, only_category=category)
    fresh = [it for it in items
             if not is_duplicate(it["title"], existing)
             and not is_near_duplicate(it["title"], existing_hashes)]
    fresh.sort(key=lambda x: x["published"], reverse=True)
    if not fresh:
        log.warning("Tidak ada berita segar untuk %s — fallback evergreen.",
                    category)
        return run_evergreen_fallback(category, existing, existing_hashes,
                                      state, args)
    it = fresh[0]
    related = find_related(it, items)
    log.info("Topik: %s | pendukung: %d (%s)",
             it["title"][:60], len(related),
             ", ".join(r["source"] for r in related) or "-")
    bahan = "\n".join(
        f"- [{b['source']}] {b['title']}\n  Ringkasan: {b['summary'][:350]}"
        for b in [it] + related
    )
    task = (
        "Bahan berita (kumpulkan FAKTANYA saja, jangan salin kalimatnya):\n\n"
        f"{bahan}\n\n"
        "Tugas: tulis artikel berita original dalam Bahasa Indonesia, gaya "
        "kritis-analitis seperti jurnalis investigasi. JANGAN copy kalimat dari "
        "sumber. Tambahkan konteks 'mengapa ini penting' dan 'apa yang tidak "
        "dikatakan media mainstream'. 400-500 kata."
        + OUTPUT_FORMAT_TAIL
    )
    return write_article(task, category, 1 + len(related), SYSTEM_PROMPT,
                         existing, existing_hashes, state, args)


def run_sejarah(existing, existing_hashes, state, args):
    """Sejarah: Wikipedia on-this-day -> artikel 'Peristiwa Hari Ini'.
    Gagal -> antrean evergreen."""
    ev = fetch_onthisday(state)
    if not ev:
        log.warning("on-this-day kosong — fallback evergreen sejarah.")
        return run_evergreen("sejarah", existing, existing_hashes, state, args)
    bahan = f"Peristiwa tahun {ev['year']}: {ev['text']}"
    extra = archive_enrichment(ev["text"][:60])
    if extra:
        bahan += f"\n\nKonteks tambahan dari arsip digital:\n{extra}"
    task = (
        f"Bahan sejarah:\n\n{bahan}\n\n"
        "Tugas: tulis artikel 'Hari Ini Dalam Sejarah' dalam Bahasa Indonesia "
        f"tentang peristiwa tahun {ev['year']} di atas. Hidupkan narasinya, "
        "jelaskan konteks dan mengapa peristiwa ini masih relevan hari ini. "
        "Bedakan fakta terdokumentasi dari legenda. 400-500 kata."
        + OUTPUT_FORMAT_TAIL
    )
    made = write_article(task, "sejarah", 2, SEJARAH_SYSTEM_PROMPT,
                         existing, existing_hashes, state, args)
    if args.dry_run:
        return 0  # dry-run: skip bukan kegagalan, jangan fallback
    if not made:
        return run_evergreen("sejarah", existing, existing_hashes, state, args)
    return made


def run_konspirasi(existing, existing_hashes, state, args):
    """Konspirasi/misteri: thread terpanas PullPush -> bedah bukti.
    Gagal -> antrean evergreen."""
    p = fetch_pullpush(state)
    if not p:
        log.warning("PullPush kosong — fallback evergreen konspirasi.")
        return run_evergreen("konspirasi", existing, existing_hashes,
                             state, args)
    bahan = (f"Thread r/{p['subreddit']} (skor {p['score']}): {p['title']}\n"
             f"Isi diskusi: {p['selftext'][:800]}")
    extra = archive_enrichment(p["title"][:60])
    if extra:
        bahan += f"\n\nKonteks tambahan dari arsip digital:\n{extra}"
    task = (
        f"Bahan misteri:\n\n{bahan}\n\n"
        "Tugas: bedah klaim misteri di atas dengan pisau analisis kritis. "
        "Sajikan klaimnya, bukti pendukung, penjelasan ilmiah/skeptis, dan beri "
        "label [TERBUKTI]/[BELUM TERBUKTI]/[TIDAK TERVERIFIKASI] pada tiap klaim "
        "kunci. Jangan menuduh tanpa bukti. 400-500 kata."
        + OUTPUT_FORMAT_TAIL
    )
    made = write_article(task, "konspirasi", 2, KONSPIRASI_SYSTEM_PROMPT,
                         existing, existing_hashes, state, args)
    if args.dry_run:
        return 0  # dry-run: skip bukan kegagalan, jangan fallback
    if not made:
        return run_evergreen("konspirasi", existing, existing_hashes,
                             state, args)
    return made


def run_evergreen(category, existing, existing_hashes, state, args):
    """Tulis 1 artikel dari antrean evergreen (sejarah/konspirasi)."""
    item = pop_evergreen(category, state)
    if not item:
        log.error("Evergreen %s habis dan tidak ada sumber lain.", category)
        return 0
    topic = item.get("topic", "")
    angle = item.get("angle", "")
    bahan = f"Topik: {topic}\nSudut pandang yang diminta: {angle}"
    extra = archive_enrichment(topic)
    if extra:
        bahan += f"\n\nKonteks tambahan dari arsip digital:\n{extra}"
    if category == "sejarah":
        system_prompt, task_head = SEJARAH_SYSTEM_PROMPT, (
            f"Bahan topik sejarah:\n\n{bahan}\n\n"
            "Tugas: tulis artikel sejarah populer dalam Bahasa Indonesia "
            "tentang topik di atas, ikuti sudut pandang yang diminta. Naratif "
            "hidup, bedakan fakta dari legenda. 400-500 kata."
        )
    else:
        system_prompt, task_head = KONSPIRASI_SYSTEM_PROMPT, (
            f"Bahan topik misteri:\n\n{bahan}\n\n"
            "Tugas: bedah topik misteri di atas dengan analisis kritis, ikuti "
            "sudut pandang yang diminta. Labeli tiap klaim kunci "
            "[TERBUKTI]/[BELUM TERBUKTI]/[TIDAK TERVERIFIKASI]. 400-500 kata."
        )
    return write_article(task_head + OUTPUT_FORMAT_TAIL, category, 2,
                         system_prompt, existing, existing_hashes, state, args)


def run_evergreen_fallback(failed_category, existing, existing_hashes,
                           state, args):
    """Breaking sepi -> pakai evergreen sejarah/konspirasi bergantian."""
    n = state.get("fallback_count", 0)
    cat = "sejarah" if n % 2 == 0 else "konspirasi"
    state["fallback_count"] = n + 1
    log.info("Fallback breaking(%s) -> evergreen %s", failed_category, cat)
    return run_evergreen(cat, existing, existing_hashes, state, args)

# ------------------------------------------------------------------ Groq

def groq_call(system_prompt, user_prompt, max_tokens=1600, min_wc=300):
    """Satu panggilan Groq dengan fallback model berurutan.
    v5: single-pass per artikel (hemat budget Groq free tier 200K TPD)."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        log.error("GROQ_API_KEY tidak diset — hentikan.")
        sys.exit(1)

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
                    "max_tokens": max_tokens,
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
            if wc < min_wc:
                log.warning("Artikel terlalu pendek (%d kata), tetap disimpan", wc)
            return text, model
        except Exception as e:
            last_err = e
            log.warning("Groq gagal (%s): %s", model, e)
            time.sleep(2)
    raise RuntimeError(f"Semua model Groq gagal. Terakhir: {last_err}")


def groq_generate(main_item, related, deep_dive=False):
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
            "contoh: indonesian parliament building, jakarta>\n"
            "Baris SEBELUM TERAKHIR (sebelum FOTO): GAMBAR: <deskripsi visual "
            "detail dalam BAHASA INGGRIS, 1-2 kalimat, untuk AI image generator "
            "— gambarkan scene foto jurnalistik yang paling mewakili isi artikel: "
            "siapa/apa yang terlihat, setting/lokasi, suasana, gaya foto. "
            "Contoh: A dramatic photojournalistic shot of the Indonesian parliament "
            "building in Jakarta at dusk, with protesters holding banners in the "
            "foreground, moody lighting, professional news photography>"
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
            "contoh: artificial intelligence robot, technology>\n"
            "Baris SEBELUM TERAKHIR (sebelum FOTO): GAMBAR: <deskripsi visual "
            "detail dalam BAHASA INGGRIS, 1-2 kalimat, untuk AI image generator "
            "— gambarkan scene foto jurnalistik yang paling mewakili isi artikel: "
            "siapa/apa yang terlihat, setting/lokasi, suasana, gaya foto.>"
        )

    return groq_call(system_prompt, user_prompt,
                     max_tokens=DEEP_DIVE_MAX_TOKENS if deep_dive else 1600,
                     min_wc=700 if deep_dive else 300)

# ------------------------------------------------------------------ simpan

def parse_output(text):
    """Pisahkan JUDUL: ..., badan artikel, FOTO: (keyword Inggris),
    dan GAMBAR: (deskripsi visual detail Inggris untuk AI image)."""
    lines = text.split("\n")
    title = ""
    image_keywords = ""
    image_desc = ""
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
        m2 = re.match(r"^\s*GAMBAR\s*:\s*(.+?)\s*$", ln, re.I)
        if m2:
            image_desc = m2.group(1).strip().strip("\"'")
    body = "\n".join(lines[body_start:]).strip()
    # buang baris FOTO: dan GAMBAR: dari body agar tidak tampil di artikel
    body = re.sub(r"(?m)^\s*(FOTO|GAMBAR)\s*:.*$", "", body).strip()
    # buang baris pembuka "# judul" duplikat bila model tetap menulisnya
    body = re.sub(r"^#\s+.*\n", "", body, count=1).lstrip()
    return title, body, image_keywords, image_desc


def excerpt_of(body, n=160):
    txt = re.sub(r"[#>*`\-]", "", body)
    txt = re.sub(r"\s+", " ", txt).strip()
    return (txt[:n] + "…") if len(txt) > n else txt


def make_thumbnail_url(title, category, image_desc=""):
    """Generate URL thumbnail via Pollinations.ai (gratis, tanpa API key).

    Jika ada deskripsi visual detail dari Groq (GAMBAR:), pakai itu langsung
    — jauh lebih relevan daripada keyword acak dari judul.
    Fallback: prompt generik dari keyword judul.
    """
    if image_desc and len(image_desc.strip()) >= 20:
        # Deskripsi detail dari Groq — tambah style guide saja
        prompt = (
            f"{image_desc.strip()}, professional news photography, "
            "editorial style, dramatic lighting, no text, no watermark"
        )
    else:
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
                 image_keywords="", image_desc=""):
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
        # Fallback AI: pakai deskripsi visual detail dari Groq (GAMBAR:)
        thumbnail = make_thumbnail_url(title, category, image_desc)
        photo_credit = "Ilustrasi AI / Pollinations"
        photo_source = "ai"
    excerpt = sanitize_frontmatter_value(excerpt_of(body), 200)
    img_kw_fm = sanitize_frontmatter_value(image_keywords, 120)
    img_desc_fm = sanitize_frontmatter_value(image_desc, 300)
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
        f'image_desc: "{img_desc_fm}"\n'
        f"sources_count: {n_sources}\n"
        f"model: {model}\n"
        "ai_generated: true\n"
        + ("deep_dive: true\n" if deep_dive else "")
        + "---\n"
    )
    (ARTICLES_DIR / f"{slug}.md").write_text(
        frontmatter + "\n" + body.strip() + "\n", encoding="utf-8")
    log.info("Disimpan: src/content/articles/%s.md", slug)
    return slug

# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(
        description="Nalar news pipeline v5 (1 artikel/jam, rotasi 6 kategori)")
    ap.add_argument("--dry-run", action="store_true",
                    help="coba alur tanpa panggil Groq/menyimpan")
    ap.add_argument("--deep-dive", action="store_true",
                    help="mode deep dive: 1 analisis investigatif panjang "
                         "(1000-1200 kata) dari topik multi-sumber terbesar")
    ap.add_argument("--category", default="",
                    help="paksa kategori: " + "|".join(CATEGORY_ROTATION))
    args = ap.parse_args()

    hour = datetime.now(WIB).hour
    if args.category in CATEGORY_ROTATION:
        category = args.category
    else:
        if args.category:
            log.warning("Kategori '%s' tidak dikenal — pakai rotasi.",
                        args.category)
        category = CATEGORY_ROTATION[hour % len(CATEGORY_ROTATION)]

    log.info("=== Nalar v5 mulai (%s) | kategori: %s%s ===",
             datetime.now(WIB).strftime("%Y-%m-%d %H:%M WIB"), category,
             " [MODE DEEP DIVE]" if args.deep_dive else "")

    state = load_state()
    sources = load_sources()
    existing = load_existing()
    log.info("%d artikel sudah ada di repo", len(existing))
    existing_hashes = [simhash(t) for _, t in existing if t]
    for h in state.get("seen_hashes", []):
        try:
            existing_hashes.append(int(h))
        except (TypeError, ValueError):
            pass

    if args.deep_dive:
        globals()["RECENCY_HOURS"] = DEEP_DIVE_RECENCY_HOURS
        items = collect_items(sources)
        if not items:
            log.warning("Tidak ada item RSS segar — selesai tanpa artikel.")
            return 0
        made = run_deep_dive(items, existing, args)
    elif category in BREAKING_CATEGORIES:
        made = run_breaking(category, sources, existing, existing_hashes,
                            state, args)
    elif category == "sejarah":
        made = run_sejarah(existing, existing_hashes, state, args)
    elif category == "konspirasi":
        made = run_konspirasi(existing, existing_hashes, state, args)
    else:  # pragma: no cover
        made = 0

    save_state(state)
    log.info("=== Selesai: %d artikel baru (kategori %s) ===", made, category)

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
