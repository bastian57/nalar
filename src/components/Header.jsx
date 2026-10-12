import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'

const NAV = [
  { to: '/', label: 'Beranda' },
  { to: '/kategori/politik', label: 'Politik' },
  { to: '/kategori/teknologi', label: 'Teknologi' },
  { to: '/metodologi', label: 'Metodologi' },
  { to: '/tentang', label: 'Tentang' },
]

function useTheme() {
  const [dark, setDark] = useState(() =>
    typeof document !== 'undefined'
      ? document.documentElement.classList.contains('dark')
      : false,
  )
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    try {
      localStorage.setItem('nalar-theme', dark ? 'dark' : 'light')
    } catch {
      /* abaikan */
    }
  }, [dark])
  return [dark, setDark]
}

export default function Header() {
  const [dark, setDark] = useTheme()
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()

  useEffect(() => setOpen(false), [pathname])

  const linkCls = ({ isActive }) =>
    `px-3 py-2 text-sm font-medium rounded transition-colors ${
      isActive
        ? 'text-tinta-700 dark:text-tinta-400'
        : 'text-neutral-600 hover:text-tinta-700 dark:text-neutral-300 dark:hover:text-tinta-400'
    }`

  return (
    <header className="sticky top-0 z-40 border-b border-neutral-200 bg-kertas/90 backdrop-blur dark:border-neutral-800 dark:bg-neutral-950/90">
      {/* garis aksen atas */}
      <div className="h-1 bg-tinta-600" />
      <div className="container-nalar flex h-16 items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5">
          <img src="/nalar-icon.jpg" alt="Nalar" className="h-10 w-10 rounded-full object-cover ring-2 ring-tinta-600/30" />
          <span className="font-serif text-3xl font-extrabold tracking-tight text-neutral-900 dark:text-white">
            Nalar
            <span className="text-tinta-600 dark:text-tinta-400">.</span>
          </span>
          <span className="hidden text-[11px] font-semibold uppercase tracking-[0.2em] text-neutral-500 dark:text-neutral-400 sm:inline">
            Kritis &amp; Cerdas
          </span>
        </Link>

        {/* nav desktop */}
        <nav className="hidden items-center gap-1 md:flex">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} className={linkCls} end={n.to === '/'}>
              {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          {/* toggle dark mode */}
          <button
            onClick={() => setDark(!dark)}
            aria-label="Ganti tema gelap/terang"
            className="rounded-full border border-neutral-300 p-2 text-neutral-600 transition-colors hover:border-tinta-600 hover:text-tinta-600 dark:border-neutral-700 dark:text-neutral-300 dark:hover:border-tinta-400 dark:hover:text-tinta-400"
          >
            {dark ? (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
                <path d="M12 2.25a.75.75 0 01.75.75v2.25a.75.75 0 01-1.5 0V3a.75.75 0 01.75-.75zM7.5 12a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM18.894 6.166a.75.75 0 00-1.06-1.06l-1.591 1.59a.75.75 0 101.06 1.061l1.591-1.59zM21.75 12a.75.75 0 01-.75.75h-2.25a.75.75 0 010-1.5H21a.75.75 0 01.75.75zM17.834 18.894a.75.75 0 001.06-1.06l-1.59-1.591a.75.75 0 10-1.061 1.06l1.59 1.591zM12 18a.75.75 0 01.75.75V21a.75.75 0 01-1.5 0v-2.25A.75.75 0 0112 18zM7.758 17.303a.75.75 0 00-1.061-1.06l-1.591 1.59a.75.75 0 001.06 1.061l1.591-1.59zM6 12a.75.75 0 01-.75.75H3a.75.75 0 010-1.5h2.25A.75.75 0 016 12zM6.166 7.758a.75.75 0 001.06 1.06l1.591-1.591a.75.75 0 00-1.061-1.06l-1.59 1.591z" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
                <path fillRule="evenodd" d="M9.528 1.718a.75.75 0 01.162.819A8.97 8.97 0 009 6a9 9 0 009 9 8.97 8.97 0 003.463-.69.75.75 0 01.981.98 10.503 10.503 0 01-9.694 6.46c-5.799 0-10.5-4.701-10.5-10.5 0-4.368 2.667-8.112 6.46-9.694a.75.75 0 01.818.162z" clipRule="evenodd" />
              </svg>
            )}
          </button>

          {/* hamburger mobile */}
          <button
            onClick={() => setOpen(!open)}
            aria-label="Buka menu"
            className="rounded p-2 text-neutral-700 hover:bg-neutral-200 dark:text-neutral-200 dark:hover:bg-neutral-800 md:hidden"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="h-6 w-6">
              <path strokeLinecap="round" strokeLinejoin="round" d={open ? 'M6 18L18 6M6 6l12 12' : 'M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5'} />
            </svg>
          </button>
        </div>
      </div>

      {/* nav mobile */}
      {open && (
        <nav className="border-t border-neutral-200 bg-kertas px-4 py-3 dark:border-neutral-800 dark:bg-neutral-950 md:hidden">
          <div className="flex flex-col gap-1">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === '/'}
                className={({ isActive }) =>
                  `rounded px-3 py-2.5 text-sm font-medium ${
                    isActive
                      ? 'bg-tinta-50 text-tinta-700 dark:bg-neutral-900 dark:text-tinta-400'
                      : 'text-neutral-700 hover:bg-neutral-100 dark:text-neutral-200 dark:hover:bg-neutral-900'
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </div>
        </nav>
      )}
    </header>
  )
}
