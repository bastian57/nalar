# Nalar — Portal Berita Kritis & Cerdas

Frontend portal berita otonom. Dibangun dengan **Vite + React + Tailwind CSS**.

## Cara jalan (butuh Node.js 18+)

```bash
cd nalar
npm install
npm run dev      # dev server → http://localhost:5173
npm run build    # build produksi → dist/
npm run preview  # pratinjau hasil build
```

## Deploy gratis (disarankan: Cloudflare Pages)

1. Push repo ini ke GitHub.
2. Di Cloudflare Pages → Create → hubungkan repo.
3. Build command: `npm run build` · Output dir: `dist`.
4. Dapat URL `nalar.pages.dev` — bandwidth unlimited, SSL otomatis.

## Tambah artikel baru

Cukup taruh file `.md` di `src/content/articles/` dengan frontmatter:

```md
---
title: "Judul Artikel"
date: "2026-10-13"
category: "politik"   # politik | teknologi | ekonomi | global
excerpt: "Ringkasan 1-2 kalimat."
slug: "judul-artikel-unik"
---

Isi artikel dalam Markdown...
```

Tidak perlu daftar manual — artikel otomatis terdeteksi via `import.meta.glob`.

## Struktur

```
nalar/
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
├── src/
│   ├── main.jsx          # entry + theme init + BrowserRouter
│   ├── App.jsx           # routing
│   ├── index.css         # tailwind + tipografi artikel
│   ├── lib/articles.js   # loader .md + parser markdown (tanpa dep)
│   ├── components/       # Header, Footer, ArticleCard
│   ├── pages/            # Home, Article, Category, Metodologi, Tentang
│   └── content/articles/ # artikel .md
```

## Catatan desain

- Aksen merah tua (`tinta-600 #A31621`) — tegas, jurnalistik.
- Judul pakai serif (Playfair Display → Georgia fallback) — kredibel.
- Dark mode toggle (class-based, tersimpan di localStorage).
- Mobile responsive + menu hamburger.

## Pipeline otonom (content engine)

Selain artikel manual, Nalar punya mesin penulis otomatis:

- `scripts/generate_news.py` — ambil RSS multi-sumber → Groq AI tulis ulang
  (kritis-analitis, 400-500 kata) → simpan `.md` + frontmatter
- `scripts/rss_sources.json` — daftar feed per kategori
- `.github/workflows/news-pipeline.yml` — cron tiap 6 jam, commit & push otomatis
- Artikel AI ditandai `ai_generated: true` di frontmatter

Lihat **DEPLOY.md** untuk setup repo, secret `GROQ_API_KEY`, dan Cloudflare Pages.
