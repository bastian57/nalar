import { useParams } from 'react-router-dom'
import { CATEGORIES, categoryName, getByCategory } from '../lib/articles.js'
import ArticleCard from '../components/ArticleCard.jsx'
import SeoMeta from '../components/SeoMeta.jsx'

export default function Category() {
  const { cat } = useParams()
  const slug = (cat || '').toLowerCase()
  const meta = CATEGORIES.find((c) => c.slug === slug)
  const articles = getByCategory(slug)

  return (
    <main className="container-nalar py-10">
      <SeoMeta
        title={`Kategori ${categoryName(slug)}`}
        description={meta?.desc || `Berita ${categoryName(slug)} terbaru dengan analisis tajam.`}
        url={`https://nalar-news.pages.dev/kategori/${slug}`}
      />
      <p className="text-xs font-bold uppercase tracking-[0.25em] text-tinta-600 dark:text-tinta-400">
        Kategori
      </p>
      <h1 className="mt-2 font-serif text-4xl font-extrabold text-neutral-900 dark:text-white">
        {categoryName(slug)}
      </h1>
      {meta?.desc && (
        <p className="mt-2 max-w-2xl text-neutral-600 dark:text-neutral-400">{meta.desc}</p>
      )}

      <div className="mt-8">
        {articles.length ? (
          <div className="grid gap-6 md:grid-cols-2">
            {articles.map((a) => (
              <ArticleCard key={a.slug} article={a} />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-neutral-300 p-10 text-center dark:border-neutral-700">
            <p className="font-serif text-xl font-bold">Belum ada artikel di kategori ini.</p>
            <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">
              Mesin Nalar sedang merangkum berita terbaru. Kembali lagi nanti.
            </p>
          </div>
        )}
      </div>
    </main>
  )
}
