import { useState } from 'react'
import { Link } from 'react-router-dom'
import { categoryName, formatDate, getArticles } from '../lib/articles.js'

// Stopwords Bahasa Indonesia — diabaikan saat ekstrak kata kunci judul
const STOPWORDS = new Set([
  'yang', 'dan', 'di', 'ke', 'dari', 'untuk', 'dengan', 'pada', 'adalah',
  'ini', 'itu', 'dalam', 'sebagai', 'oleh', 'akan', 'telah', 'sudah',
  'juga', 'tidak', 'ada', 'atau', 'tapi', 'namun', 'karena', 'saat',
  'setelah', 'sebelum', 'antara', 'lebih', 'sangat', 'para', 'sebuah',
  'seorang', 'mereka', 'kita', 'kami', 'saya', 'dia', 'nya', 'the',
  'jadi', 'agar', 'bisa', 'dapat', 'harus', 'kembali', 'baru', 'kini',
  'usai', 'soal', 'terkait', 'hingga', 'tanpa', 'bagi', 'serta',
  'dalam', 'atas', 'bawah', 'antara', 'sementara', 'meski', 'walau',
  'jika', 'kalau', 'bila', 'supaya', 'demi', 'tentang', 'menjadi',
])

/** Ekstrak kata kunci dari judul: kata >= 4 huruf, lowercase, tanpa stopwords. */
function keywordsOf(title) {
  const words = (title || '').toLowerCase().match(/[a-z]{4,}/g) || []
  return new Set(words.filter((w) => !STOPWORDS.has(w)))
}

/** Hitung jumlah kata kunci yang sama di dua set. */
function overlap(a, b) {
  let n = 0
  for (const w of a) if (b.has(w)) n++
  return n
}

function parseDay(iso) {
  const t = Date.parse((iso || '') + 'T00:00:00')
  return Number.isNaN(t) ? null : t
}

/**
 * Hitung topik trending:
 * - ambil artikel 48 jam terakhir (fallback 7 hari bila sepi)
 * - cluster greedy: gabung bila overlap kata kunci judul >= 2
 * - urutkan: ukuran cluster dulu, lalu tanggal terbaru
 */
function computeTrending() {
  const now = Date.now()
  const cut48 = now - 48 * 3600 * 1000
  const cut7d = now - 7 * 24 * 3600 * 1000

  const all = getArticles()
  let recent = all.filter((a) => {
    const t = parseDay(a.date)
    return t !== null && t >= cut48
  })
  if (recent.length < 2) {
    recent = all.filter((a) => {
      const t = parseDay(a.date)
      return t !== null && t >= cut7d
    })
  }
  if (!recent.length) return []

  // getArticles() sudah urut tanggal desc — cluster greedy dari yang terbaru
  const clusters = []
  for (const art of recent) {
    const kw = keywordsOf(art.title)
    let placed = false
    for (const c of clusters) {
      if (overlap(kw, c.keywords) >= 2) {
        c.articles.push(art)
        for (const w of kw) c.keywords.add(w)
        placed = true
        break
      }
    }
    if (!placed) clusters.push({ keywords: kw, articles: [art] })
  }

  clusters.sort((a, b) => {
    if (b.articles.length !== a.articles.length) return b.articles.length - a.articles.length
    return (b.articles[0].date || '').localeCompare(a.articles[0].date || '')
  })

  return clusters.slice(0, 5).map((c) => {
    const sorted = [...c.articles].sort((x, y) =>
      (y.date || '').localeCompare(x.date || ''),
    )
    return { lead: sorted[0], articles: sorted, count: sorted.length }
  })
}

export default function Trending() {
  const [topics] = useState(computeTrending)
  const [openIdx, setOpenIdx] = useState(0)

  if (!topics.length) return null

  return (
    <section className="mb-10" aria-label="Topik trending">
      <div className="mb-4 flex items-center gap-2">
        <span className="text-2xl" aria-hidden="true">
          🔥
        </span>
        <h2 className="font-serif text-2xl font-bold text-neutral-900 dark:text-white">
          Trending
        </h2>
        <span className="rounded-full bg-tinta-600 px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide text-white">
          Live
        </span>
      </div>

      <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        {topics.map((t, i) => {
          const open = openIdx === i
          return (
            <div
              key={t.lead.slug}
              className={
                i > 0 ? 'border-t border-neutral-200 dark:border-neutral-800' : ''
              }
            >
              <button
                type="button"
                onClick={() => setOpenIdx(open ? -1 : i)}
                aria-expanded={open}
                className="flex w-full items-center gap-3 px-4 py-4 text-left transition-colors hover:bg-tinta-50 dark:hover:bg-neutral-800/60 sm:gap-4 sm:px-5"
              >
                <span
                  aria-hidden="true"
                  className="w-10 shrink-0 text-center font-serif text-3xl font-extrabold text-tinta-600 dark:text-tinta-400 sm:text-4xl"
                >
                  {i + 1}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-serif text-base font-bold leading-snug text-neutral-900 dark:text-white sm:whitespace-normal sm:text-lg">
                    {t.lead.title}
                  </span>
                  <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-neutral-500 dark:text-neutral-400">
                    <span className="font-semibold uppercase tracking-wide text-tinta-700 dark:text-tinta-400">
                      {categoryName(t.lead.category)}
                    </span>
                    <span aria-hidden="true">·</span>
                    <span>{formatDate(t.lead.date)}</span>
                    <span aria-hidden="true">·</span>
                    <span>
                      {t.count} artikel terkait
                    </span>
                  </span>
                </span>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                  aria-hidden="true"
                  className={`h-5 w-5 shrink-0 text-neutral-400 transition-transform duration-200 dark:text-neutral-500 ${
                    open ? 'rotate-180' : ''
                  }`}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M19.5 8.25l-7.5 7.5-7.5-7.5"
                  />
                </svg>
              </button>

              {open && (
                <div className="border-t border-neutral-100 bg-neutral-50 px-4 py-3 dark:border-neutral-800 dark:bg-neutral-950/60 sm:px-5">
                  <ul className="space-y-1 sm:ml-[3.5rem]">
                    {t.articles.map((a) => (
                      <li key={a.slug}>
                        <Link
                          to={`/artikel/${a.slug}`}
                          className="group flex items-start gap-2 rounded px-2 py-1.5 text-sm transition-colors hover:bg-white dark:hover:bg-neutral-900"
                        >
                          <span
                            aria-hidden="true"
                            className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-tinta-600 dark:bg-tinta-400"
                          />
                          <span>
                            <span className="font-medium text-neutral-800 group-hover:text-tinta-700 dark:text-neutral-200 dark:group-hover:text-tinta-400">
                              {a.title}
                            </span>
                            <span className="ml-2 whitespace-nowrap text-xs text-neutral-400 dark:text-neutral-500">
                              {formatDate(a.date)} · {a.readingMinutes} mnt
                            </span>
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )
        })}
      </div>

      <p className="mt-2 text-xs text-neutral-400 dark:text-neutral-500">
        Dihitung otomatis dari liputan 48 jam terakhir — makin banyak media
        membahas satu isu, makin panas posisinya.
      </p>
    </section>
  )
}
