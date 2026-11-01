#!/usr/bin/env node
/**
 * Nalar — OG prerender (v5.3).
 *
 * MASALAH: crawler WhatsApp/Telegram/Twitter TIDAK menjalankan JavaScript.
 * Mereka hanya membaca HTML mentah dari URL. Karena Nalar adalah SPA, semua
 * URL (/artikel/<slug>) menyajikan index.html yang sama -> crawler selalu
 * dapat judul situs + logo, bukan judul & gambar artikel.
 *
 * SOLUSI: script ini jalan SETELAH `vite build` (lihat package.json).
 * Untuk setiap artikel, ia membuat dist/artikel/<slug>/index.html = salinan
 * index.html hasil build dengan tag OG/Twitter/<title> diganti ke data
 * artikel itu. Cloudflare Pages menyajikan file statis tersebut untuk
 * /artikel/<slug> (file statis menang atas SPA fallback), sementara browser
 * manusia tetap mendapat SPA normal (bundle JS sama, router tetap jalan).
 *
 * Tanpa dependensi eksternal — hanya fs/path Node bawaan.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DIST = path.join(ROOT, 'dist');
const ARTICLES_DIR = path.join(ROOT, 'src', 'content', 'articles');
const SITE = 'https://nalar-news.pages.dev';
const FALLBACK_IMAGE = `${SITE}/nalar-icon.jpg`;

function escAttr(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/** Parser frontmatter minimal (format: key: value, nilai boleh dikutip). */
function parseFrontmatter(text) {
  const m = text.match(/^---\s*\n([\s\S]*?)\n---\s*\n/);
  if (!m) return {};
  const fm = {};
  for (const line of m[1].split('\n')) {
    const mm = line.match(/^(\w+):\s*(.*)$/);
    if (!mm) continue;
    let v = mm[2].trim();
    if ((v.startsWith('"') && v.endsWith('"')) ||
        (v.startsWith("'") && v.endsWith("'"))) {
      v = v.slice(1, -1);
    }
    fm[mm[1]] = v;
  }
  return fm;
}

/** Ganti content dari satu tag <meta property|name="X" ... />. */
function replaceMeta(html, attr, key, value) {
  const re = new RegExp(
    `<meta\\s+${attr}="${key}"\\s+content="[^"]*"\\s*/?>`,
  );
  if (!re.test(html)) {
    console.warn(`  ! tag ${attr}="${key}" tidak ditemukan di index.html`);
    return html;
  }
  return html.replace(
    re,
    `<meta ${attr}="${key}" content="${escAttr(value)}" />`,
  );
}

function main() {
  const indexPath = path.join(DIST, 'index.html');
  if (!fs.existsSync(indexPath)) {
    console.error('OG prerender GAGAL: dist/index.html tidak ada. Jalankan vite build dulu.');
    process.exit(1);
  }
  const shell = fs.readFileSync(indexPath, 'utf-8');

  const files = fs.readdirSync(ARTICLES_DIR).filter((f) => f.endsWith('.md'));
  let ok = 0;
  let skipped = 0;

  for (const file of files) {
    const fm = parseFrontmatter(
      fs.readFileSync(path.join(ARTICLES_DIR, file), 'utf-8'),
    );
    const slug = fm.slug || file.replace(/\.md$/, '');
    const title = fm.title || slug;
    const excerpt = fm.excerpt || '';
    const thumb = fm.thumbnail || '';
    const image = thumb.startsWith('http') ? thumb : FALLBACK_IMAGE;
    const url = `${SITE}/artikel/${slug}`;
    const fullTitle = `${title} — Nalar`;

    let html = shell;
    html = html.replace(/<title>[^<]*<\/title>/, `<title>${escAttr(fullTitle)}</title>`);
    html = replaceMeta(html, 'name', 'description', excerpt);
    html = replaceMeta(html, 'property', 'og:type', 'article');
    html = replaceMeta(html, 'property', 'og:title', title);
    html = replaceMeta(html, 'property', 'og:description', excerpt);
    html = replaceMeta(html, 'property', 'og:image', image);
    html = replaceMeta(html, 'property', 'og:url', url);
    html = replaceMeta(html, 'name', 'twitter:title', title);
    html = replaceMeta(html, 'name', 'twitter:description', excerpt);
    html = replaceMeta(html, 'name', 'twitter:image', image);
    // Tag article: opsional, disisipkan setelah og:url
    const extra = [
      fm.date ? `<meta property="article:published_time" content="${escAttr(fm.date)}" />` : '',
      fm.category ? `<meta property="article:section" content="${escAttr(fm.category)}" />` : '',
    ].filter(Boolean).join('\n    ');
    if (extra) {
      html = html.replace(
        /(<meta property="og:url" content="[^"]*" \/>)/,
        `$1\n    ${extra}`,
      );
    }

    const outDir = path.join(DIST, 'artikel', slug);
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, 'index.html'), html, 'utf-8');
    ok++;
    if (!thumb.startsWith('http')) skipped++;
  }

  console.log(`OG prerender: ${ok} artikel -> dist/artikel/<slug>/index.html` +
    (skipped ? ` (${skipped} pakai logo fallback, tanpa thumbnail)` : ''));
}

main();
