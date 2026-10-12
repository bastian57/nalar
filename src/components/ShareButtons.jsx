import { useState } from 'react'

export default function ShareButtons({ title, slug }) {
  const [copied, setCopied] = useState(false)
  const url = `https://nalar-news.pages.dev/artikel/${slug}`
  const text = encodeURIComponent(title)

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* abaikan */
    }
  }

  const btn =
    'flex items-center gap-1.5 rounded-full border border-neutral-300 px-3.5 py-1.5 text-sm font-medium text-neutral-700 transition-colors hover:border-tinta-600 hover:text-tinta-600 dark:border-neutral-700 dark:text-neutral-300 dark:hover:border-tinta-400 dark:hover:text-tinta-400'

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm font-semibold text-neutral-500 dark:text-neutral-400">
        Bagikan:
      </span>
      <a
        href={`https://wa.me/?text=${text}%20${encodeURIComponent(url)}`}
        target="_blank"
        rel="noopener noreferrer"
        className={btn}
      >
        WhatsApp
      </a>
      <a
        href={`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${text}`}
        target="_blank"
        rel="noopener noreferrer"
        className={btn}
      >
        Telegram
      </a>
      <a
        href={`https://twitter.com/intent/tweet?text=${text}&url=${encodeURIComponent(url)}`}
        target="_blank"
        rel="noopener noreferrer"
        className={btn}
      >
        X
      </a>
      <button onClick={copyLink} className={btn}>
        {copied ? '✓ Tersalin!' : 'Salin Link'}
      </button>
    </div>
  )
}
