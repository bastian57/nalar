import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="mt-16 border-t border-neutral-200 bg-neutral-100 dark:border-neutral-800 dark:bg-neutral-900">
      <div className="container-nalar grid gap-10 py-12 md:grid-cols-3">
        <div>
          <p className="font-serif text-2xl font-extrabold text-neutral-900 dark:text-white">
            Nalar<span className="text-tinta-600 dark:text-tinta-400">.</span>
          </p>
          <p className="mt-3 text-sm leading-6 text-neutral-600 dark:text-neutral-400">
            Portal berita kritis dan independen. Merangkum peristiwa dari berbagai media,
            lalu menulis ulang dengan analisis tajam — agar pembaca tidak sekadar tahu,
            tapi paham.
          </p>
        </div>
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
            Navigasi
          </p>
          <ul className="mt-3 space-y-2 text-sm">
            <li><Link className="hover:text-tinta-600 dark:hover:text-tinta-400" to="/">Beranda</Link></li>
            <li><Link className="hover:text-tinta-600 dark:hover:text-tinta-400" to="/kategori/politik">Politik</Link></li>
            <li><Link className="hover:text-tinta-600 dark:hover:text-tinta-400" to="/kategori/teknologi">Teknologi</Link></li>
            <li><Link className="hover:text-tinta-600 dark:hover:text-tinta-400" to="/metodologi">Metodologi</Link></li>
            <li><Link className="hover:text-tinta-600 dark:hover:text-tinta-400" to="/tentang">Tentang Nalar</Link></li>
            <li><a className="hover:text-tinta-600 dark:hover:text-tinta-400" href="/rss.xml" target="_blank" rel="noopener">📡 RSS Feed</a></li>
          </ul>
        </div>
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
            Transparansi
          </p>
          <p className="mt-3 text-sm leading-6 text-neutral-600 dark:text-neutral-400">
            Artikel di Nalar dirangkum dan dianalisis dengan bantuan kecerdasan buatan
            dari berbagai sumber media. Baca selengkapnya di halaman{' '}
            <Link className="font-medium text-tinta-600 underline dark:text-tinta-400" to="/metodologi">
              Metodologi
            </Link>
            .
          </p>
        </div>
      </div>
      <div className="border-t border-neutral-200 dark:border-neutral-800">
        <div className="container-nalar flex flex-col items-center justify-between gap-2 py-5 text-xs text-neutral-500 dark:text-neutral-500 sm:flex-row">
          <span>© 2026 Nalar. Berpikir kritis adalah hak semua orang.</span>
          <span>Dibangun dengan Vite + React.</span>
        </div>
      </div>
    </footer>
  )
}
