import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  // Same-origin API in dev: no CORS needed. 127.0.0.1, not localhost (IPv6 stall on Windows).
  // host: Vite's default "localhost" can bind IPv6 only ([::1]), but email links, APP_URL and the tests use 127.0.0.1.
  server: { host: '127.0.0.1', proxy: { '/api': 'http://127.0.0.1:8000' } },
})
