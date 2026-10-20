/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        orbe: {
          teal: '#0e5a6b',
          'teal-hover': '#0a4552',
          accent: '#dcecef',
          'accent-text': '#0a4552',
          success: '#1e7a45',
          incident: '#3d1714',
          'incident-text': '#f47066',
          bg: '#f5f6f4',
          page: '#faf9f5',
          border: '#d5dcdf',
          text: '#0f1a1d',
          muted: '#55636a',
        },
      },
    },
  },
  plugins: [],
}
