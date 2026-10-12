import { useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { getArticles } from '../lib/articles.js'
import ArticleCard from '../components/ArticleCard.jsx'

function searchArticles(query) {
  const q = query.toLowerCase().trim()
  if (!q) return []
  const words = q.split(/\s+/)
  return getArticles()
    .map((a) => {
      const hay = `${a.title} ${a.excerpt} ${a.body || ''}`.toLowerCase()
      let score = 0
      for (const w of words) {
        if (a.title.toLowerCase().includes(w)) score += 3
        else if (hay.includes(w)) score += 1
      }
      return { a, score }
    })
    .filter((x) => x.score > 0)
    .sort((x, y) => y.score - x.score)
    .map((x) => x.a)
}

export default function Search() {
  const [params] = useSearchParams()
  const q = params.get('q') || ''
  const results = useMemo(() => searchArticles(q), [q])

  return (
    <main className="container-nalar py-10">
      <h1 className="font-serif text-3xl font-bold text-neutral-900 dark:text-white">
        Hasil pencarian
      </h1>
      <p className="mt-2 text-neutral-600 dark:text-neutral-400">
        {q ? (
          <>
            <span className="font-semibold text-tinta-600 dark:text-tinta-400">“{q}”</span>
            {' — '}ditemukan {results.length} artikel
          </>
        ) : (
          'Ketik kata kunci di kolom pencarian.'
        )}
      </p>
      {q && results.length === 0 && (
        <p className="mt-8 text-neutral-500">
          Tidak ada hasil. Coba kata kunci lain.
        </p>
      )}
      <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {results.map((a) => (
          <ArticleCard key={a.slug} article={a} />
        ))}
      </div>
      <p className="mt-10">
        <Link to="/" className="text-sm font-medium text-tinta-600 hover:underline dark:text-tinta-400">
          ← Kembali ke Beranda
        </Link>
      </p>
    </main>
  )
}
