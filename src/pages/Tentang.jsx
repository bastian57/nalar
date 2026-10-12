import { Link } from 'react-router-dom'

export default function Tentang() {
  return (
    <main className="container-nalar py-10">
      <div className="mx-auto max-w-3xl">
        <p className="text-xs font-bold uppercase tracking-[0.25em] text-tinta-600 dark:text-tinta-400">
          Tentang Kami
        </p>
        <h1 className="mt-2 font-serif text-4xl font-extrabold text-neutral-900 dark:text-white">
          Apa itu Nalar?
        </h1>

        <hr className="my-8 border-neutral-200 dark:border-neutral-800" />

        <div className="article-body">
          <p>
            <strong>Nalar</strong> adalah portal berita yang lahir dari kegelisahan sederhana:
            terlalu banyak berita hari ini ditulis untuk memancing klik, bukan untuk
            membuat pembaca paham. Judul bombastis, isi tipis, analisis nol.
          </p>
          <p>
            Kami percaya pembaca Indonesia layak mendapatkan yang lebih baik —
            ringkasan yang jujur, analisis yang berani, dan sudut pandang yang tidak
            tunduk pada kepentingan pemilik modal media.
          </p>

          <h2>Visi</h2>
          <p>
            Menjadi ruang baca bagi mereka yang menolak dibodohi: kritis, independen,
            ter-aktual — dan yang terpenting, <strong>mencerdaskan</strong>.
          </p>

          <h2>Misi</h2>
          <ul>
            <li>Menyajikan rangkuman peristiwa yang padat dan jujur, tanpa sensasionalisme.</li>
            <li>Membedah framing media: menunjukkan apa yang ditonjolkan dan apa yang disembunyikan.</li>
            <li>Menggunakan teknologi kecerdasan buatan secara transparan untuk mempercepat kerja redaksi.</li>
            <li>Tetap independen — tidak dibiayai pihak yang kami kritik.</li>
          </ul>

          <h2>Siapa di balik Nalar?</h2>
          <p>
            Nalar dikelola secara independen dengan bantuan teknologi AI untuk perangkuman
            dan penulisan. Keputusan editorial — apa yang layak terbit dan bagaimana
            sebuah isu dibedah — mengikuti standar yang ditetapkan manusia, bukan
            sekadar keluaran mesin.
          </p>

          <blockquote>
            Berpikir kritis adalah hak semua orang. Nalar ada untuk menjaganya.
          </blockquote>

          <p>
            Ingin memahami cara kerja kami lebih dalam? Baca{' '}
            <Link className="text-tinta-600 underline dark:text-tinta-400" to="/metodologi">
              metodologi Nalar
            </Link>
            .
          </p>
        </div>
      </div>
    </main>
  )
}
