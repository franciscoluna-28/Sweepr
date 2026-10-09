import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// In dev the UI proxies API calls to the backend. Locally that's 127.0.0.1;
// in Docker Compose it's the `api` service hostname.
const apiTarget =
  process.env.VITE_API_PROXY ??
  `http://127.0.0.1:${process.env.MEOWLESS_PORT ?? 8765}`

export default defineConfig({
  plugins: [tailwindcss(), svelte()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    // Windows bind mounts don't emit file events; enable polling in Docker.
    watch: { usePolling: process.env.CHOKIDAR_USEPOLLING === 'true' },
    proxy: { '/api': apiTarget },
  },
  build: { outDir: 'dist' },
})
