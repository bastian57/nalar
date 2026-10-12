import { useEffect } from 'react'

const SITE = 'https://nalar-news.pages.dev'
const DEFAULT_IMG = `${SITE}/nalar-icon.jpg`

function setMeta(attr, key, content) {
  let el = document.querySelector(`meta[${attr}="${key}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

/**
 * Update <title> dan meta tags (OG/Twitter/description) secara dinamis
 * saat navigasi antar halaman. Membantu SEO dan pratinjau share.
 */
export default function SeoMeta({ title, description, image, url, type = 'website' }) {
  useEffect(() => {
    const fullTitle = title ? `${title} — Nalar` : 'Nalar — Berita Kritis & Cerdas'
    document.title = fullTitle

    const desc = description || 'Portal berita kritis, independen, dan mencerdaskan. Dirangkum dari berbagai media, dianalisis dengan tajam.'
    const img = image || DEFAULT_IMG
    const pageUrl = url || SITE

    setMeta('name', 'description', desc)
    setMeta('property', 'og:type', type)
    setMeta('property', 'og:site_name', 'Nalar')
    setMeta('property', 'og:title', fullTitle)
    setMeta('property', 'og:description', desc)
    setMeta('property', 'og:image', img)
    setMeta('property', 'og:url', pageUrl)
    setMeta('name', 'twitter:card', 'summary_large_image')
    setMeta('name', 'twitter:title', fullTitle)
    setMeta('name', 'twitter:description', desc)
    setMeta('name', 'twitter:image', img)

    // canonical link
    let canon = document.querySelector('link[rel="canonical"]')
    if (!canon) {
      canon = document.createElement('link')
      canon.setAttribute('rel', 'canonical')
      document.head.appendChild(canon)
    }
    canon.setAttribute('href', pageUrl)
  }, [title, description, image, url, type])

  return null
}
