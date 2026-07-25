import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  base: '/ui/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/dashboard': 'http://127.0.0.1:8000',
      '/shop-records': 'http://127.0.0.1:8000',
      '/custom-fields': 'http://127.0.0.1:8000',
      '/license-records': 'http://127.0.0.1:8000',
      '/admin-users': 'http://127.0.0.1:8000',
      '/admin': 'http://127.0.0.1:8000',
      '/uploads': 'http://127.0.0.1:8000',
    },
  },
})
