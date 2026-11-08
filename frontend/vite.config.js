import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'HealthConnect Ghana',
        short_name: 'HealthConnect',
        description: 'Connecting rural patients and CHVs with health facilities',
        theme_color: '#0c3322',
        background_color: '#fafaf9',
        display: 'standalone',
        orientation: 'portrait',
        scope: '/',
        start_url: '/',
        icons: [
          { src: 'favicon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
        ],
      },
      workbox: {
        // Cache the app itself (HTML/JS/CSS) so it opens offline.
        // API replies are NOT cached: they contain patient data.
        globPatterns: ['**/*.{js,css,html,svg}'],
      },
    }),
  ],
})
