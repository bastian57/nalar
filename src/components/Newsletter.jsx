import { useState } from 'react'

/**
 * Form langganan newsletter Nalar.
 * Versi 1: simpan ke localStorage (tanpa backend).
 * TODO: sambungkan ke Buttondown/Mailchimp/Substack saat sudah ada akun.
 */
export default function Newsletter() {
  const [email, setEmail] = useState('')
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')

  const submit = (e) => {
    e.preventDefault()
    const v = email.trim().toLowerCase()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) {
      setError('Masukkan alamat email yang valid.')
      return
    }
    try {
      const key = 'nalar-newsletter'
      const list = JSON.parse(localStorage.getItem(key) || '[]')
      if (!list.includes(v)) {
        list.push(v)
        localStorage.setItem(key, JSON.stringify(list))
      }
      setDone(true)
      setError('')
    } catch {
      setError('Gagal menyimpan. Coba lagi.')
    }
  }

  return (
    <section className="mb-10 rounded-2xl border border-tinta-600/20 bg-gradient-to-br from-tinta-50 to-white p-8 dark:from-neutral-900 dark:to-neutral-950 dark:border-tinta-400/20">
      <div className="mx-auto max-w-xl text-center">
        <p className="text-2xl">📬</p>
        <h2 className="mt-2 font-serif text-2xl font-bold text-neutral-900 dark:text-white">
          Dapatkan analisis tajam tiap pagi
        </h2>
        <p className="mt-2 text-sm leading-6 text-neutral-600 dark:text-neutral-400">
          Ringkasan berita terpenting + satu analisis mendalam, dikirim ke email Anda.
          Gratis, tanpa spam.
        </p>
        {done ? (
          <p className="mt-4 rounded-lg bg-green-50 px-4 py-3 text-sm font-medium text-green-700 dark:bg-green-900/20 dark:text-green-400">
            ✓ Terdaftar! Anda akan jadi yang pertama tahu saat newsletter diluncurkan.
          </p>
        ) : (
          <form onSubmit={submit} className="mt-4 flex flex-col gap-2 sm:flex-row">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="nama@email.com"
              className="flex-1 rounded-full border border-neutral-300 bg-white px-5 py-2.5 text-sm text-neutral-800 placeholder-neutral-400 outline-none focus:border-tinta-600 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:focus:border-tinta-400"
            />
            <button
              type="submit"
              className="rounded-full bg-tinta-600 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-tinta-700"
            >
              Langganan
            </button>
          </form>
        )}
        {error && <p className="mt-2 text-xs text-red-600 dark:text-red-400">{error}</p>}
        <p className="mt-3 text-[11px] text-neutral-400 dark:text-neutral-500">
          Dengan mendaftar, Anda menyetujui kebijakan privasi Nalar.
        </p>
      </div>
    </section>
  )
}
