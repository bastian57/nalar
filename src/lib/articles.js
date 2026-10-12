/**
 * Mesin artikel Nalar — tanpa dependensi eksternal.
 * Memuat file .md dari src/content/articles/ via import.meta.glob (?raw),
 * mem-parsing frontmatter, dan me-render markdown minimal menjadi HTML.
 */

// Muat semua artikel sebagai teks mentah (eager agar bisa diakses sinkron)
const rawModules = import.meta.glob('../content/articles/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
})

const esc = (s) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

function inlineMd(s) {
  let t = esc(s)
  t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  t = t.replace(/(^|[^*\w])\*([^*\n]+)\*/g, '$1<em>$2</em>')
  t = t.replace(/`([^`]+)`/g, '<code>$1</code>')
  return t
}

/** Konversi subset Markdown → HTML (heading, bold/italic, quote, list, paragraf). */
export function mdToHtml(src) {
  const lines = src.split('\n')
  let html = ''
  let para = []
  let listType = null

  const flushPara = () => {
    if (para.length) {
      html += `<p>${inlineMd(para.join(' '))}</p>`
      para = []
    }
  }
  const closeList = () => {
    if (listType) {
      html += listType === 'ul' ? '</ul>' : '</ol>'
      listType = null
    }
  }

  for (const rawLine of lines) {
    const line = rawLine.replace(/\s+$/, '')
    const trimmed = line.trim()
    if (!trimmed) {
      flushPara()
      closeList()
      continue
    }
    let m
    if ((m = trimmed.match(/^(#{1,4})\s+(.*)/))) {
      flushPara()
      closeList()
      const lvl = m[1].length
      html += `<h${lvl}>${inlineMd(m[2])}</h${lvl}>`
    } else if (/^---+$/.test(trimmed)) {
      flushPara()
      closeList()
      html += '<hr/>'
    } else if ((m = trimmed.match(/^>\s?(.*)/))) {
      flushPara()
      closeList()
      html += `<blockquote>${inlineMd(m[1])}</blockquote>`
    } else if ((m = trimmed.match(/^[-*]\s+(.*)/))) {
      flushPara()
      if (listType !== 'ul') {
        closeList()
        html += '<ul>'
        listType = 'ul'
      }
      html += `<li>${inlineMd(m[1])}</li>`
    } else if ((m = trimmed.match(/^\d+\.\s+(.*)/))) {
      flushPara()
      if (listType !== 'ol') {
        closeList()
        html += '<ol>'
        listType = 'ol'
      }
      html += `<li>${inlineMd(m[1])}</li>`
    } else {
      closeList()
      para.push(trimmed)
    }
  }
  flushPara()
  closeList()
  return html
}

/** Parse frontmatter YAML sederhana (key: value satu baris). */
function parseFrontmatter(raw) {
  const match = raw.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/)
  if (!match) return { meta: {}, body: raw }
  const meta = {}
  for (const line of match[1].split('\n')) {
    const idx = line.indexOf(':')
    if (idx > 0) {
      const key = line.slice(0, idx).trim()
      let val = line.slice(idx + 1).trim()
      if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
        val = val.slice(1, -1)
      }
      meta[key] = val
    }
  }
  return { meta, body: match[2].trim() }
}

function fileToSlug(path) {
  const base = path.split('/').pop() || ''
  return base.replace(/\.md$/, '')
}

function safeThumbnailUrl(url) {
  // Hanya izinkan http/https — tolak javascript:, data:, dll.
  if (typeof url !== 'string') return ''
  const t = url.trim()
  if (/^https?:\/\//i.test(t)) return t
  return ''
}

const articles = Object.entries(rawModules)
  .map(([path, raw]) => {
    const { meta, body } = parseFrontmatter(raw)
    const slug = meta.slug || fileToSlug(path)
    return {
      slug,
      title: meta.title || slug,
      date: meta.date || '',
      category: (meta.category || 'umum').toLowerCase(),
      excerpt: meta.excerpt || '',
      thumbnail: safeThumbnailUrl(meta.thumbnail),
      deepDive: meta.deep_dive === 'true' || meta.deep_dive === true,
      body,
      html: mdToHtml(body),
      readingMinutes: Math.max(1, Math.round(body.split(/\s+/).length / 200)),
    }
  })
  .sort((a, b) => (b.date || '').localeCompare(a.date || ''))

export const CATEGORIES = [
  { slug: 'politik', name: 'Politik', desc: 'Kuasa, kebijakan, dan siapa yang diuntungkan.' },
  { slug: 'teknologi', name: 'Teknologi', desc: 'AI, platform digital, dan masa depan yang datang lebih cepat.' },
  { slug: 'ekonomi', name: 'Ekonomi', desc: 'Uang, pasar, dan dapur rakyat.' },
  { slug: 'olahraga', name: 'Olahraga', desc: 'Lapangan, skor, dan drama di luar nalar.' },
  { slug: 'global', name: 'Global', desc: 'Dunia di luar pagar.' },
]

export function categoryName(slug) {
  return CATEGORIES.find((c) => c.slug === slug)?.name || slug
}

export function getArticles() {
  return articles
}

export function getArticle(slug) {
  return articles.find((a) => a.slug === slug)
}

export function getByCategory(cat) {
  return articles.filter((a) => a.category === cat.toLowerCase())
}

export function isDeepDive(article) {
  return !!article?.deepDive
}

export function getDeepDives() {
  return articles.filter(isDeepDive)
}

export function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso + 'T00:00:00').toLocaleDateString('id-ID', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    })
  } catch {
    return iso
  }
}
