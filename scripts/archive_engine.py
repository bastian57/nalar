#!/usr/bin/env python3
"""
Nalar — archive_engine (v5).

Jembatan ke Internet Archive (archive.org) — gratis, tanpa API key:
1. search_archive()   : cari item (teks/gambar/video) via Advanced Search API
2. get_item_text()    : ambil cuplikan teks full dari sebuah item
3. wayback_snapshot() : snapshot terdekat sebuah URL (Wayback Machine)
4. CLI --bank         : bangun daftar kandidat topik evergreen

Dipakai generate_news.py untuk memperkaya bahan artikel sejarah/konspirasi.
Semua fungsi defensif: gagal -> [] / "" / None, tidak menggagalkan run.
"""

import argparse
import json
import logging
import sys
from urllib.parse import quote

import requests

log = logging.getLogger("archive_engine")

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    )
}

ADV_SEARCH = "https://archive.org/advancedsearch.php"
METADATA = "https://archive.org/metadata/"
WAYBACK_AVAILABLE = "https://archive.org/wayback/available"


def _get(url, params=None, timeout=25):
    r = requests.get(url, params=params, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.json()


def search_archive(query, mediatype="texts", rows=5, sort="downloads desc"):
    """Cari item archive.org. Return list {identifier,title,description,date}."""
    try:
        q = f"({query}) AND mediatype:{mediatype}"
        data = _get(ADV_SEARCH, params={
            "q": q,
            "fl[]": ["identifier", "title", "description", "date", "creator"],
            "rows": rows,
            "output": "json",
            "sort[]": sort,
        })
        out = []
        for d in data.get("response", {}).get("docs", []):
            out.append({
                "identifier": d.get("identifier", ""),
                "title": d.get("title", ""),
                "description": (d.get("description") or "")[:600],
                "date": d.get("date", ""),
                "creator": d.get("creator", ""),
            })
        return out
    except Exception as e:
        log.warning("search_archive gagal (%s): %s", query[:40], e)
        return []


def get_item_text(identifier, max_chars=3000):
    """Ambil cuplikan teks full (_djvu.txt) dari sebuah item."""
    if not identifier:
        return ""
    try:
        meta = _get(METADATA + quote(identifier, safe=""))
        files = meta.get("files", [])
        target = None
        for f in files:
            name = f.get("name", "")
            if name.endswith("_djvu.txt"):
                target = name
                break
        if not target:
            return ""
        url = f"https://archive.org/download/{quote(identifier, safe='')}/{quote(target, safe='/')}"
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        txt = r.text
        return txt[:max_chars]
    except Exception as e:
        log.warning("get_item_text gagal (%s): %s", identifier, e)
        return ""


def wayback_snapshot(url, timestamp=""):
    """Snapshot Wayback terdekat untuk sebuah URL. Return URL snapshot/None."""
    try:
        params = {"url": url}
        if timestamp:
            params["timestamp"] = timestamp
        data = _get(WAYBACK_AVAILABLE, params=params, timeout=25)
        snap = (data.get("archived_snapshots") or {}).get("closest") or {}
        if snap.get("available"):
            return snap.get("url")
        return None
    except Exception as e:
        log.warning("wayback_snapshot gagal (%s): %s", url[:60], e)
        return None


def main():
    ap = argparse.ArgumentParser(description="Nalar archive_engine")
    ap.add_argument("--bank", default="",
                    help="bangun kandidat topik evergreen: sejarah|konspirasi")
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%H:%M:%S")

    if not args.bank:
        ap.print_help()
        return 0

    seeds = {
        "sejarah": "history indonesia world war ancient civilization",
        "konspirasi": "mystery unexplained conspiracy declassified",
    }
    q = seeds.get(args.bank, args.bank)
    hits = search_archive(q, rows=args.n)
    print(json.dumps(hits, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
