import { Link } from 'react-router-dom'
import { categoryName, formatDate } from '../lib/articles.js'

export default function ArticleCard({ article, featured = false }) {
  return (
    <Link
      to={`/artikel/${article.slug}`}
      className={`group flex flex-col overflow-hidden rounded-xl border border-neutral-200 bg-white transition-all hover:-translate-y-0.5 hover:shadow-lg dark:border-neutral-800 dark:bg-neutral-900 ${
        featured ? 'md:col-span-2 md:flex-row' : ''
      }`}
    >
      {/* thumbnail tipografis */}
      <div
        className={`flex items-center justify-center bg-gradient-to-br from-tinta-700 via-tinta-600 to-neutral-900 p-6 ${
          featured ? 'md:w-2/5' : 'h-36'
        }`}
      >
        <span className="text-center font-serif text-lg font-bold leading-snug text-white line-clamp-4">
          {article.title}
        </span>
      </div>
      <div className={`flex flex-1 flex-col p-5 ${featured ? 'md:p-8' : ''}`}>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {article.deepDive && (
            <span className="rounded-full bg-amber-400 px-2.5 py-1 text-[11px] font-extrabold uppercase tracking-widest text-amber-950 ring-1 ring-amber-600/50 shadow-sm">
              ✦ Deep Dive
            </span>
          )}
          <span className="rounded-full bg-tinta-50 px-2.5 py-1 font-semibold uppercase tracking-wide text-tinta-700 dark:bg-neutral-800 dark:text-tinta-400">
            {categoryName(article.category)}
          </span>
          <span className="text-neutral-500 dark:text-neutral-400">{formatDate(article.date)}</span>
          <span className="text-neutral-400 dark:text-neutral-500">· {article.readingMinutes} mnt baca</span>
        </div>
        <h3
          className={`mt-3 font-serif font-bold leading-snug text-neutral-900 transition-colors group-hover:text-tinta-700 dark:text-white dark:group-hover:text-tinta-400 ${
            featured ? 'text-2xl md:text-3xl' : 'text-lg'
          }`}
        >
          {article.title}
        </h3>
        <p className="mt-2 flex-1 text-sm leading-6 text-neutral-600 line-clamp-3 dark:text-neutral-400">
          {article.excerpt}
        </p>
        <span className="mt-4 text-sm font-semibold text-tinta-600 dark:text-tinta-400">
          Baca analisis →
        </span>
      </div>
    </Link>
  )
}
