import { Link } from 'react-router-dom'
import { CATEGORIES, getArticles } from '../lib/articles.js'
import ArticleCard from '../components/ArticleCard.jsx'

export default function Home() {
  const articles = getArticles()
  const [featured, ...rest] = articles

  return (
    <main className="container-nalar py-10">
      {/* hero */}
      <section className="mb-10 border-b-2 border-tinta-600 pb-8">
        <p className="text-xs font-bold uppercase tracking-[0.25em] text-tinta-600 dark:text-tinta-400">
          Portal Berita Kritis &amp; Cerdas
        </p>
        <h1 className="mt-2 max-w-3xl font-serif text-4xl font-extrabold leading-tight text-neutral-900 dark:text-white sm:text-5xl">
          Jangan sekadar tahu. <span className="text-tinta-700 dark:text-tinta-400">Pahami.</span>
        </h1>
        <p className="mt-3 max-w-2xl text-neutral-600 dark:text-neutral-400">
          Nalar merangkum peristiwa dari berbagai media, lalu menulis ulang dengan
          analisis tajam dan independen — agar Anda membaca dengan nalar, bukan emosi.
        </p>
      </section>

      {/* artikel utama */}
      {featured ? (
        <section className="mb-10">
          <p className="mb-4 text-xs font-bold uppercase tracking-[0.2em] text-neutral-500">
            Sorotan Utama
          </p>
          <ArticleCard article={featured} featured />
        </section>
      ) : (
        <p className="mb-10 text-neutral-500">Belum ada artikel.</p>
      )}

      {/* kategori */}
      <section className="mb-10">
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map((c) => (
            <Link
              key={c.slug}
              to={`/kategori/${c.slug}`}
              className="rounded-full border border-neutral-300 px-4 py-1.5 text-sm font-medium text-neutral-700 transition-colors hover:border-tinta-600 hover:text-tinta-700 dark:border-neutral-700 dark:text-neutral-300 dark:hover:border-tinta-400 dark:hover:text-tinta-400"
            >
              {c.name}
            </Link>
          ))}
        </div>
      </section>

      {/* daftar terbaru */}
      <section>
        <h2 className="mb-5 font-serif text-2xl font-bold text-neutral-900 dark:text-white">
          Terbaru
        </h2>
        {rest.length ? (
          <div className="grid gap-6 md:grid-cols-2">
            {rest.map((a) => (
              <ArticleCard key={a.slug} article={a} />
            ))}
          </div>
        ) : (
          !featured && <p className="text-neutral-500">Belum ada artikel lain.</p>
        )}
      </section>
    </main>
  )
}
