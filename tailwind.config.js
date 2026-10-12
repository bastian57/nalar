/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Playfair Display"', 'Georgia', '"Times New Roman"', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        tinta: {
          50: '#fdf2f3',
          100: '#fbe5e6',
          200: '#f7c0c4',
          300: '#f09299',
          400: '#e45f6a',
          500: '#d43a46',
          600: '#A31621', // accent utama — merah tua tegas
          700: '#8a1220',
          800: '#6e0f1d',
          900: '#570c18',
        },
        kertas: '#faf8f5',
      },
    },
  },
  plugins: [],
}
