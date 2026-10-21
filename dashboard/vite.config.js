import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // La page Documentation lit les .md du dossier docs/ du dépôt (hors de dashboard/)
    fs: { allow: ['..'] },
    // En dev, /bo/* est relayé vers bo-api (docker-compose.dev.yml), comme le fera le Nginx
    // du dashboard en démonstration : même origine, pas de CORS.
    proxy: {
      '/bo': 'http://localhost:8006',
    },
  },
})
