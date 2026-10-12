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


# ---------------------------------------------------------------- main

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
