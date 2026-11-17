import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In dev the UI proxies API calls to a locally running `sweepr --no-browser`.
// changeOrigin makes the backend see its own Host header (loopback allowlist).
const apiTarget = process.env.VITE_API_PROXY ?? `http://127.0.0.1:${process.env.SWEEPR_PORT ?? 8765}`

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: { '/api': { target: apiTarget, changeOrigin: true } },
  },
  build: { outDir: 'dist', sourcemap: false },
})
