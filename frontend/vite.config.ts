import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backend = 'http://127.0.0.1:8000'

// Every backend prefix the PC console calls. Listed explicitly rather than
// proxying `/` so the dev server keeps serving its own assets and HMR. Note
// `/ui` is deliberately absent: it is this app's own base path.
const apiPrefixes = [
  '/account-usage-records',
  '/admin',
  '/admin-users',
  '/api',
  '/article-publisher',
  '/audit-logs',
  '/auth',
  '/company-expenses',
  '/custom-fields',
  '/dashboard',
  '/dingtalk-profits',
  '/expense-categories',
  '/health',
  '/knowledge-api',
  '/license-admin',
  '/license-records',
  '/mobile-devices',
  '/peer-shops',
  '/reader',
  '/saved-links',
  '/shop-records',
  '/software-admin',
  '/system-alerts',
  '/task-bookkeeping',
  '/ui-settings',
  '/uploads',
  '/warehouse',
]

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
    proxy: Object.fromEntries(apiPrefixes.map((prefix) => [prefix, backend])),
  },
})
