#!/usr/bin/env python3
"""
Nalar Smart Image Engine — foto asli berlisensi bebas untuk thumbnail artikel.

Urutan pencarian (berhenti di yang pertama dapat hasil):
  1. Wikimedia Commons API  — foto editorial asli, lisensi CC / domain publik
  2. Openverse API          — agregator foto berlisensi CC
  3. (fallback di pemanggil) Pollinations.ai — ilustrasi AI

Semua sumber di atas LEGAL untuk dipakai ulang tanpa bayar.

Fungsi utama:
  fetch_smart_image(title, category, keywords) -> (url, credit, source)
  Gagal total -> (None, "", "") — pemanggil lalu pakai Pollinations.

Dipakai oleh generate_news.py saat menyimpan artikel baru. Foto lama
(Pollinations) tidak diubah — hanya artikel baru yang memakai engine ini.
"""

import logging
import re
from urllib.parse import quote

import requests

log = logging.getLogger("nalar.image")

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}
TIMEOUT = 12

# Kata kunci Inggris per kategori — Commons/Openverse jauh lebih akurat
# dengan query Inggris daripada Indonesia.
CATEGORY_EN = {
    "politik": "indonesia politics government",
    "teknologi": "technology artificial intelligence",
    "ekonomi": "economy finance market",
    "olahraga": "sports stadium",
    "global": "world news",
    "umum": "news press",
}

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s):
    """Buang tag HTML dari nama artis Commons (sering berupa <a href>)."""
    return _TAG_RE.sub("", s or "").strip()


def _clean_credit(s, maxlen=120):
    s = _strip_html(s)
    s = re.sub(r"\s+", " ", s).strip()
    # buang "unknown author" — bukan kredit yang berguna, tampilkan sumber saja
    if "unknown" in s.lower():
        return ""
    # buang karakter yang bisa merusak frontmatter YAML
    s = s.replace('"', "'").replace("\\", "").replace("\n", " ")
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)
    return s[:maxlen]


# ---------------------------------------------------------------- Commons

# Ekstensi foto asli — tolak PDF/SVG/audio/video yang kadang nyangkut
# di hasil pencarian Commons (thumbnail-nya tidak cocok untuk berita).
_PHOTO_EXT = (".jpg", ".jpeg", ".png", ".webp")


def _is_photo(page, info):
    title = (page.get("title") or "").lower()
    orig = (info.get("url") or "").lower()
    return title.endswith(_PHOTO_EXT) or orig.endswith(_PHOTO_EXT)


def commons_search(query, limit=8):
    """Cari gambar bebas lisensi di Wikimedia Commons.

    Mengembalikan list dict: {url, artist, license}.
    Hanya file foto asli (.jpg/.png/.webp) — bukan PDF/SVG/media lain.
    """
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap",
        "gsrnamespace": 6,          # namespace File:
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 800,          # thumbnail 800px (cukup untuk kartu)
    }
    r = requests.get(url, params=params, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    pages = (r.json().get("query") or {}).get("pages") or {}
    out = []
    for p in pages.values():
        info = (p.get("imageinfo") or [{}])[0]
        if not _is_photo(p, info):
            continue
        thumb = info.get("thumburl") or info.get("url")
        if not thumb or not thumb.startswith("http"):
            continue
        meta = info.get("extmetadata") or {}
        artist = _clean_credit((meta.get("Artist") or {}).get("value", ""))
        lic = (meta.get("LicenseShortName") or {}).get("value", "")
        out.append({"url": thumb, "artist": artist, "license": lic})
    return out


# ---------------------------------------------------------------- Openverse

def openverse_search(query, limit=5):
    """Cari foto CC di Openverse (api.openverse.org).

    Mengembalikan list dict: {url, artist, license}.
    """
    url = "https://api.openverse.org/v1/images/"
    params = {
        "q": query,
        "license_type": "all",
        "page_size": limit,
        "filter_dead": True,
    }
    r = requests.get(url, params=params, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for it in (r.json().get("results") or []):
        img = it.get("url")
        if not img or not img.startswith("http"):
            continue
        out.append({
            "url": img,
            "artist": _clean_credit(it.get("creator") or ""),
            "license": (it.get("license") or "").upper(),
        })
    return out


# ---------------------------------------------------------------- Wikipedia
# v3: Wikipedia JADI SUMBER UTAMA. Lead image artikel Wikipedia dikurasi
# editor — jauh lebih relevan daripada Commons search mentah.
# Query Bahasa Indonesia di id.wikipedia untuk entitas lokal.

def wikipedia_search(query, lang="id", limit=3):
    """Cari lead image artikel Wikipedia.

    Mengembalikan list dict: {url, title}. Hanya yang punya thumbnail.
    """
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": limit,
        "prop": "pageimages",
        "formatversion": 2,
        "pithumbsize": 800,
    }
    r = requests.get(url, params=params, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    pages = (r.json().get("query") or {}).get("pages") or []
    out = []
    for p in pages:
        thumb = (p.get("thumbnail") or {}).get("source")
        if not thumb or not thumb.startswith("http"):
            continue
        out.append({"url": thumb, "title": p.get("title", "")})
    return out


def id_wiki_queries(title, category):
    """Susun query Wikipedia Bahasa Indonesia dari judul.

    Prioritas: istilah kamus yang muncul di judul (sinyal kuat),
    lalu kata-kata panjang dari judul.
    """
    queries = []
    low = (title or "").lower()
    # istilah kamus yang muncul -> query langsung (mis. "dpr", "kucing")
    hits = [k for k in ID_EN_PHOTO if k in low and len(k) >= 3]
    # utamakan yang lebih panjang/spesifik dulu
    for h in sorted(hits, key=len, reverse=True)[:2]:
        queries.append(h)
    # kata-kata panjang dari judul sebagai query umum
    words = [w for w in re.findall(r"[a-zA-Z]{4,}", low)
             if w not in ("yang", "dari", "dengan", "untuk", "pada",
                          "adalah", "ini", "itu", "dan", "atau", "dalam")]
    if words:
        queries.append(" ".join(words[:4]))
    return list(dict.fromkeys(queries))
# Kamus istilah berita Indonesia -> Inggris untuk pencarian foto.
# Dipakai backfill artikel lama (yang tidak punya image_keywords dari Groq).
# Artikel BARU memakai keyword Inggris langsung dari Groq (lebih presisi).
ID_EN_PHOTO = {
    # politik & pemerintahan
    "dpr": "indonesian parliament", "parlemen": "parliament",
    "presiden": "indonesian president", "istana": "presidential palace jakarta",
    "pemilu": "indonesia election voting", "pilkada": "indonesia local election",
    "menteri": "minister government", "gubernur": "governor",
    "bupati": "regent indonesia", "walikota": "mayor city",
    "kpk": "anti-corruption", "korupsi": "corruption",
    "polisi": "indonesian police", "tni": "indonesian military army",
    "satpol": "public order officer", "demo": "protest demonstration",
    # ekonomi
    "emas": "gold bullion", "rupiah": "indonesian rupiah currency",
    "saham": "stock market trading", "inflasi": "inflation economy",
    "umkm": "small business indonesia", "pertanian": "agriculture rice field",
    "nelayan": "fisherman boat", "pasar": "traditional market",
    "kementan": "agriculture ministry", "mentan": "agriculture minister",
    "penyuluh": "agricultural extension worker",
    # teknologi
    "kecerdasan": "artificial intelligence robot", "robot": "robot",
    "ai": "artificial intelligence robot",
    "siber": "cybersecurity", "digital": "digital technology",
    "startup": "startup office", "internet": "internet network",
    # bencana & sosial
    "gempa": "earthquake", "banjir": "flood", "kebakaran": "fire",
    "longsor": "landslide",
    # umum
    "sekolah": "school indonesia", "kampus": "university",
    "masjid": "mosque", "gereja": "church",
    "sepak": "football soccer", "timnas": "indonesia national football team",
    "stadion": "stadium", "mandalika": "mandalika circuit",
    "kucing": "cat", "hewan": "pet animal", "peliharaan": "pet",
    "tidur": "sleeping bed", "kesehatan": "health hospital",
}


def id_to_en_keywords(title, category):
    """Terjemahkan kata kunci judul Indonesia -> Inggris untuk cari foto.

    Mengembalikan set keyword Inggris. Dipakai backfill artikel lama.
    """
    out = set()
    low = (title or "").lower()
    for id_word, en in ID_EN_PHOTO.items():
        if id_word in low:
            out.update(en.split())
    # tambah keyword kategori sebagai jaring pengaman
    cat_q = CATEGORY_EN.get((category or "umum").lower(), "")
    out.update(cat_q.split())
    return {w for w in out if len(w) >= 3}

# NOTE 2026-10-12: Unsplash (napi endpoint, tanpa key) DICORET dari chain —
# sekarang dipagari bot-check ("Making sure you're not a bot", HTTP 401)
# untuk akses server-side. Chain: Commons -> Openverse -> Pollinations.
# Pexels/Pixabay bisa ditambahkan di sini nanti bila Putra daftar API key gratis.

_SOURCES = (
    ("wikimedia", commons_search, "Wikimedia Commons"),
    ("openverse", openverse_search, "Openverse"),
)


def _build_queries(title, category, keywords):
    """Susun query: kata kunci judul dulu, lalu fallback kategori (Inggris)."""
    queries = []
    kw = " ".join(sorted({w for w in (keywords or []) if len(w) >= 4})[:4])
    if kw:
        queries.append(kw)
    cat_q = CATEGORY_EN.get((category or "umum").lower(), "news")
    queries.append(cat_q)
    # dedup, pertahankan urutan
    return list(dict.fromkeys(queries))


def _credit(source_label, artist):
    if artist:
        return f"{source_label} / {artist}"
    return source_label


def fetch_smart_image(title, category, keywords):
    """Cari foto asli berlisensi bebas untuk sebuah artikel.

    Urutan (v2, teruji stabil):
      1. Wikimedia Commons search — keyword Inggris (dari Groq/kamus).
      2. Openverse — foto CC.

    Wikipedia lead image TIDAK dipakai otomatis (hasil campur aduk di tes) —
    hanya via fix manual untuk kasus spesifik.

    Returns:
        (url, credit, source) — source salah satu dari
        {"wikimedia", "openverse"}.
        Gagal total -> (None, "", "") — pemanggil pakai fallback AI.
    """
    for q in _build_queries(title, category, keywords):
        for source_key, fn, label in _SOURCES:
            try:
                results = fn(q)
            except Exception as e:  # noqa: BLE001 — satu sumber mati, lanjut
                log.warning("smart_image: %s gagal untuk %r: %s", source_key, q, e)
                continue
            if results:
                r = results[0]
                credit = _credit(label, r["artist"])
                log.info("smart_image: %s -> %s (%s)", q, source_key, credit)
                return r["url"], credit, source_key
    log.info("smart_image: tidak ada foto untuk %r — pakai fallback AI", title[:40])
    return None, "", ""
