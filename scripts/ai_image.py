#!/usr/bin/env python3
"""
Nalar — Ilustrasi AI via Pollinations (v5.4).

Perubahan v5.4: ilustrasi AI menjadi SUMBER GAMBAR UTAMA, bukan fallback
terakhir. Alasannya: foto stok (Wikimedia/Openverse) hanya cocok dengan
1-4 keyword generik ("economy", "business") sehingga gambar sering tidak
nyambung dengan cerita spesifik. Ilustrasi AI dibangun dari topik + angle
artikel itu sendiri, jadi relevansinya melekat sejak lahir.

Alur per artikel (di save_article):
  1. Bangun prompt dari deskripsi visual Groq (GAMBAR:) / judul + excerpt.
  2. Buat URL Pollinations (Flux, 1280x720, seed deterministik dari slug).
  3. Warming: GET URL sekali (maks 90 dtk) untuk memastikan Pollinations
     hidup sekaligus menghangatkan cache CDN-nya. Sukses -> pakai URL ini.
  4. Gagal -> fallback foto stok (fetch_smart_image).
  5. Stok juga gagal -> URL Pollinations tanpa warming (usaha terakhir).

Gratis, tanpa API key, tanpa storage (URL Pollinations = CDN-nya).
Label kejujuran: photo_credit selalu "Ilustrasi AI / Pollinations" untuk
gambar AI, dan gaya prompt adalah ILUSTRASI editorial — bukan foto palsu.
"""
import logging
import re
import zlib
from urllib.parse import quote

import requests

log = logging.getLogger("nalar-ai-image")

WIDTH = 1280
HEIGHT = 720
MODEL = "flux"
AI_CREDIT = "Ilustrasi AI / Pollinations"

_STYLE = (
    "modern digital illustration style, muted professional color palette, "
    "dramatic composition, clear focal subject, "
    "no text, no watermark, no logo"
)


def build_illustration_prompt(title, category, image_desc="", excerpt=""):
    """Susun prompt ilustrasi editorial dari topik artikel.

    Prioritas adegan: deskripsi visual Groq (GAMBAR:) -> judul + lead excerpt.
    Kategori hanya konteks trailing, BUKAN subjek utama (itu yang dulu
    bikin gambar generik: prompt "economy" -> foto bisnis acak).
    """
    scene = ""
    if image_desc and len(image_desc.strip()) >= 20:
        scene = re.sub(r"\s+", " ", image_desc.strip())[:300]
    else:
        parts = [title.strip()]
        if excerpt:
            parts.append(re.sub(r"\s+", " ", excerpt.strip())[:160])
        scene = ". ".join(p for p in parts if p)[:320]
    if not scene:
        scene = title.strip() or "news"
    cat = (category or "").strip().lower()
    prompt = f"Editorial news illustration, {scene}"
    if cat:
        prompt += f", {cat} news context"
    prompt += f", {_STYLE}"
    return prompt


def pollinations_url(prompt, slug):
    """URL Pollinations deterministik: slug yang sama -> seed yang sama
    -> gambar yang sama (stabil saat rebuild/backfill)."""
    seed = zlib.crc32((slug or "nalar").encode("utf-8")) % 1000000
    encoded = quote(prompt, safe="")
    return (
        "https://image.pollinations.ai/prompt/"
        f"{encoded}?width={WIDTH}&height={HEIGHT}"
        f"&nologo=true&model={MODEL}&seed={seed}"
    )


def warm_pollinations(url, timeout=90):
    """GET sekali untuk memastikan Pollinations hidup + menghangatkan cache.

    Return True bila respons 200 dengan Content-Type image/*.
    Gagal/timeout -> False (pemanggil pakai fallback), bukan error fatal.
    """
    try:
        r = requests.get(url, timeout=timeout)
        ct = r.headers.get("Content-Type", "")
        if r.status_code == 200 and ct.startswith("image/"):
            log.info("Pollinations OK (%d bytes)", len(r.content))
            return True
        log.warning("Pollinations respons tak valid: %s %s",
                    r.status_code, ct)
    except Exception as e:  # noqa: BLE001 — semua gagal = fallback
        log.warning("Pollinations gagal: %s", e)
    return False
