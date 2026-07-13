import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['marka_logo.jpg'],
      manifest: {
        name: 'MARKA - Keep the Paper, Eliminate the Marking',
        short_name: 'MARKA',
        description: 'Blazing fast physical exam grading.',
        theme_color: '#000000',
        background_color: '#ffffff',
        display: 'standalone',
        icons: [
          {
            src: 'marka_logo.jpg',
            sizes: '512x512',
            type: 'image/jpeg'
          }
        ]
      },
      workbox: {
        // Precache only content-hashed, immutable assets — NOT index.html.
        // (index.html changes every deploy but keeps the same URL, so
        // cache-first precaching of it serves a stale app after each deploy.)
        globPatterns: ['**/*.{js,css,ico,png,svg,webp,woff2}'],
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        skipWaiting: true,
        navigateFallback: null,
        runtimeCaching: [
          {
            // The HTML document is served network-first: online users always
            // get the freshly deployed index.html (and thus the latest hashed
            // JS), falling back to the cached copy only when offline.
            urlPattern: ({ request }) => request.mode === 'navigate',
            handler: 'NetworkFirst',
            options: {
              cacheName: 'html-shell',
              networkTimeoutSeconds: 3,
              expiration: { maxEntries: 10 },
            },
          },
        ],
      }
    })
  ]
})

