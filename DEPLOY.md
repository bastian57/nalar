# DEPLOY — Portal Berita Nalar

Panduan dari nol sampai portal jalan otonom. Semua gratis (zero budget).

## 1. Buat repo GitHub

1. Buka https://github.com/new
2. Owner: **bastian57**, Repository name: **nalar**, pilih **Public**
3. Jangan centang "Add a README" (repo lokal sudah ada)
4. Create repository

## 2. Push code

Di folder `~/workspace/nalar`:

```bash
cd ~/workspace/nalar
git init -b main
git add .
git commit -m "Nalar: portal + pipeline otonom"
git remote add origin https://github.com/bastian57/nalar.git
git push -u origin main
```

> ⚠️ **PENTING — file workflow harus diupload manual.**
> Koneksi GitHub yang dipakai punya keterbatasan izin `workflows`
> (kasus sama seperti repo AIR KITA). Kalau push di atas menolak file
> `.github/workflows/news-pipeline.yml`, upload manual:
> GitHub web → repo **nalar** → **Add file → Upload files** →
> pilih `nalar/.github/workflows/news-pipeline.yml` → Commit.

## 3. Tambah GROQ_API_KEY ke Secrets

Gratis di https://console.groq.com → API Keys → Create.

1. Repo **nalar** → **Settings → Secrets and variables → Actions**
2. **New repository secret**
3. Name: `GROQ_API_KEY`, Secret: paste key dari console.groq.com
4. Add secret

Tanpa ini, pipeline gagal dengan log `GROQ_API_KEY tidak diset`.

## 4. Tes pipeline manual

1. Tab **Actions** → **Nalar News Pipeline**
2. **Run workflow → Run workflow**
3. Tunggu ±3-5 menit → cek tab **Code → src/content/articles/**:
   artikel `.md` baru harus muncul.

Kalau gagal, buka log run-nya — semua aktivitas dicatat
(`Gagal fetch ...` untuk RSS mati itu normal, dilewati otomatis).

## 5. Connect ke Cloudflare Pages

1. https://dash.cloudflare.com → **Workers & Pages → Create → Pages**
2. **Connect to Git** → pilih repo **bastian57/nalar**
3. Build settings:
   - Framework preset: **Vite**
   - Build command: `npm run build`
   - Build output directory: `dist`
4. Save and Deploy → dapat URL `https://nalar.pages.dev`

Setiap push (termasuk commit otomatis dari pipeline) → Cloudflare
rebuild otomatis. Artikel baru terbit tanpa sentuh apa-apa.

## 6. Jadwal produksi

| UTC | WIB | Isi |
|-----|-----|-----|
| 00:00 | 07:00 | 3-5 artikel pagi |
| 06:00 | 13:00 | 3-5 artikel siang |
| 12:00 | 19:00 | 3-5 artikel sore |
| 18:00 | 01:00 | 3-5 artikel dini hari |

Maks ~20 artikel/hari. Groq free tier cukup untuk volume ini.

## 7. Uji lokal (opsional, tanpa Groq)

```bash
pip install feedparser requests
# coba RSS + dedup saja, tanpa panggil AI:
python scripts/generate_news.py --dry-run --max 3
```

## Catatan

- Artikel AI ditandai `ai_generated: true` di frontmatter.
- Halaman Metodologi di frontend menjelaskan cara kerja Nalar
  (rangkum multi-sumber → tulis ulang + analisis original).
- Jangan pernah commit API key ke repo. Hanya via Secrets.
