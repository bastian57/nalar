import { useEffect, useRef } from 'react'

/**
 * Kolom komentar Nalar via giscus (gratis, menempel ke GitHub Discussions).
 *
 * CARA AKTIFKAN (2 menit, sekali saja — Putra yang eksekusi):
 *  1. github.com/bastian57/nalar → Settings → centang "Discussions"
 *  2. Buka https://giscus.app → masukkan repo "bastian57/nalar"
 *  3. Copy "repo ID" dan buat category "Komentar" → copy "category ID"
 *  4. Paste keduanya di GISCUS_CONFIG bawah, push, redeploy.
 *
 * Selama ID masih kosong, komponen ini me-render null (tidak ada error,
 * tidak ada ruang kosong) — situs tetap jalan normal tanpa komentar.
 */
const GISCUS_CONFIG = {
  repo: 'bastian57/nalar',
  repoId: '', // <-- paste repo ID dari giscus.app
  category: 'Komentar',
  categoryId: '', // <-- paste category ID dari giscus.app
}

export default function Giscus() {
  const ref = useRef(null)
  const ready = Boolean(GISCUS_CONFIG.repoId && GISCUS_CONFIG.categoryId)

  useEffect(() => {
    if (!ready || !ref.current || ref.current.hasChildNodes()) return
    const s = document.createElement('script')
    s.src = 'https://giscus.app/client.js'
    s.async = true
    s.crossOrigin = 'anonymous'
    s.setAttribute('data-repo', GISCUS_CONFIG.repo)
    s.setAttribute('data-repo-id', GISCUS_CONFIG.repoId)
    s.setAttribute('data-category', GISCUS_CONFIG.category)
    s.setAttribute('data-category-id', GISCUS_CONFIG.categoryId)
    s.setAttribute('data-mapping', 'pathname')
    s.setAttribute('data-strict', '0')
    s.setAttribute('data-reactions-enabled', '1')
    s.setAttribute('data-emit-metadata', '0')
    s.setAttribute('data-input-position', 'bottom')
    s.setAttribute('data-theme', 'preferred_color_scheme')
    s.setAttribute('data-lang', 'id')
    ref.current.appendChild(s)
  }, [ready])

  if (!ready) return null

  return (
    <section className="mt-10 border-t border-neutral-200 pt-8 dark:border-neutral-800">
      <h2 className="mb-4 font-serif text-xl font-bold text-neutral-900 dark:text-white">
        Diskusi
      </h2>
      <div ref={ref} className="giscus" />
    </section>
  )
}
