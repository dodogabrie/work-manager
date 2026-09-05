import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'

/* In sviluppo il backend è servito dallo stesso origin tramite proxy: niente
   CORS da configurare e il cookie di sessione (SameSite=lax) funziona come in
   produzione. VITE_API_BASE resta vuoto e le chiamate partono relative. */
const BACKEND = process.env.BACKEND_ORIGIN ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/calendar': { target: BACKEND, changeOrigin: true },
    },
  },
})
