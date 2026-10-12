import { Link, useParams } from 'react-router-dom'
import { categoryName, formatDate, getArticle, getByCategory } from '../lib/articles.js'
import ArticleCard from '../components/ArticleCard.jsx'

export default function Article() {
  const { slug } = useParams()
  const article = getArticle(slug)

  if (!article) {
    return (
      <main className="container-nalar py-24 text-center">
        <h1 className="font-serif text-3xl font-bold">Artikel tidak ditemukan</h1>
        <p className="mt-2 text-neutral-600 dark:text-neutral-400">
          Mungkin slug-nya salah, atau artikel sudah dihapus.
        </p>
        <Link to="/" className="mt-6 inline-block rounded bg-tinta-600 px-6 py-2.5 font-semibold text-white hover:bg-tinta-700">
          Kembali ke Beranda
        </Link>
      </main>
    )
  }

  const related = getByCategory(article.category)
    .filter((a) => a.slug !== article.slug)
    .slice(0, 2)

  return (
    <main className="container-nalar py-10">
      <article className="mx-auto max-w-3xl">
        {article.thumbnail && (
          <img
            src={article.thumbnail}
            alt={article.title}
            loading="lazy"
            onError={(e) => {
              e.currentTarget.style.display = 'none'
            }}
            className="mb-8 aspect-video w-full rounded-xl object-cover shadow-md"
          />
        )}

        <div className="flex items-center gap-3 text-xs">
          <Link
            to={`/kategori/${article.category}`}
            className="rounded-full bg-tinta-50 px-3 py-1 font-semibold uppercase tracking-wide text-tinta-700 dark:bg-neutral-800 dark:text-tinta-400"
          >
            {categoryName(article.category)}
          </Link>
          <span className="text-neutral-500 dark:text-neutral-400">{formatDate(article.date)}</span>
          <span className="text-neutral-400">· {article.readingMinutes} menit baca</span>
        </div>

        <h1 className="mt-4 font-serif text-3xl font-extrabold leading-tight text-neutral-900 dark:text-white sm:text-4xl">
          {article.title}
        </h1>
        <p className="mt-4 font-serif text-lg italic leading-8 text-neutral-600 dark:text-neutral-400">
          {article.excerpt}
        </p>

        <hr className="my-8 border-neutral-200 dark:border-neutral-800" />

        <div className="article-body dropcap" dangerouslySetInnerHTML={{ __html: article.html }} />

        <div className="mt-10 rounded-xl border border-neutral-200 bg-neutral-100 p-5 text-sm leading-6 text-neutral-600 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-400">
          <p className="font-semibold text-neutral-800 dark:text-neutral-200">Catatan redaksi</p>
          <p className="mt-1">
            Artikel ini dirangkum dari berbagai sumber media dan ditulis ulang dengan
            analisis oleh Nalar. Baca <Link className="text-tinta-600 underline dark:text-tinta-400" to="/metodologi">metodologi kami</Link> untuk
            memahami cara kerja redaksi.
          </p>
        </div>
      </article>

      {related.length > 0 && (
        <section className="mx-auto mt-14 max-w-3xl">
          <h2 className="mb-5 font-serif text-2xl font-bold">Terkait</h2>
          <div className="grid gap-6 md:grid-cols-2">
            {related.map((a) => (
              <ArticleCard key={a.slug} article={a} />
            ))}
          </div>
        </section>
      )}
    </main>
  )
}
