/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

// Base path is configurable so the same code serves '/' (live) and '/Jal-rakshak/' (GitHub Pages demo).
export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), ''), ...process.env };
  const base = env.VITE_BASE || '/';
  const backend = env.JR_BACKEND_URL || 'http://localhost:8000';

  return {
    base,
    plugins: [
      react(),
      VitePWA({
        registerType: 'autoUpdate',
        injectRegister: null, // registered manually in src/pwa.ts (skipped in tests / dev)
        includeAssets: ['favicon.svg', 'icons/apple-touch-icon.png'],
        manifest: {
          name: 'JalRakshak — Flood Early Warning',
          short_name: 'JalRakshak',
          description:
            'Agentic flood early-warning and response decision support for Indian cities.',
          theme_color: '#0f172a',
          background_color: '#0b1220',
          display: 'standalone',
          start_url: '.',
          scope: '.',
          lang: 'en-IN',
          icons: [
            { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
            { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
            { src: 'icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          ],
        },
        workbox: {
          // App shell + demo scenario are precached so the demo works fully offline.
          globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2,json,webmanifest}'],
          maximumFileSizeToCacheInBytes: 12 * 1024 * 1024,
          navigateFallback: 'index.html',
          navigateFallbackDenylist: [/^\/api\//],
          runtimeCaching: [
            {
              urlPattern: ({ url }) => url.hostname.endsWith('tile.openstreetmap.org'),
              handler: 'StaleWhileRevalidate',
              options: {
                cacheName: 'osm-tiles',
                expiration: { maxEntries: 600, maxAgeSeconds: 60 * 60 * 24 * 14 },
                cacheableResponse: { statuses: [0, 200] },
              },
            },
            {
              urlPattern: ({ url, request }) =>
                request.method === 'GET' && url.pathname.startsWith('/api/') && !url.pathname.endsWith('.pdf'),
              handler: 'NetworkFirst',
              options: {
                cacheName: 'api-get',
                networkTimeoutSeconds: 5,
                expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 3 },
                cacheableResponse: { statuses: [200] },
              },
            },
          ],
        },
      }),
    ],
    server: {
      port: 5173,
      proxy: { '/api': { target: backend, changeOrigin: true } },
    },
    preview: {
      port: 4173,
      proxy: { '/api': { target: backend, changeOrigin: true } },
    },
    build: {
      target: 'es2020',
      chunkSizeWarningLimit: 900,
      rollupOptions: {
        output: {
          manualChunks: (id) => {
            if (id.includes('node_modules/leaflet') || id.includes('node_modules/react-leaflet') || id.includes('@react-leaflet')) return 'leaflet';
            if (id.includes('node_modules/recharts') || id.includes('node_modules/d3-') || id.includes('node_modules/victory-vendor')) return 'charts';
            return undefined;
          },
        },
      },
    },
    test: {
      environment: 'jsdom',
      globals: false,
      setupFiles: ['./src/test/setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
      css: false,
    },
  };
});
