import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Header from './components/Header.jsx'
import Footer from './components/Footer.jsx'
import Home from './pages/Home.jsx'
import Article from './pages/Article.jsx'
import Category from './pages/Category.jsx'
import Metodologi from './pages/Metodologi.jsx'
import Tentang from './pages/Tentang.jsx'

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

function NotFound() {
  return (
    <main className="container-nalar py-24 text-center">
      <p className="font-serif text-7xl font-bold text-tinta-600 dark:text-tinta-400">404</p>
      <h1 className="mt-4 font-serif text-2xl font-bold">Halaman tidak ditemukan</h1>
      <p className="mt-2 text-neutral-600 dark:text-neutral-400">
        Nalar tidak menemukan apa yang Anda cari. Mungkin sudah dihapus, atau memang tidak pernah ada.
      </p>
      <a href="/" className="mt-6 inline-block rounded bg-tinta-600 px-6 py-2.5 font-semibold text-white hover:bg-tinta-700">
        Kembali ke Beranda
      </a>
    </main>
  )
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <ScrollToTop />
      <Header />
      <div className="flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/artikel/:slug" element={<Article />} />
          <Route path="/kategori/:cat" element={<Category />} />
          <Route path="/metodologi" element={<Metodologi />} />
          <Route path="/tentang" element={<Tentang />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </div>
      <Footer />
    </div>
  )
}
