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

// The knowledge base is a separate service (`knowledge-base.service`, see
// deploy/nginx/xiaoxu.conf.template), not part of the FastAPI backend. It serves
// its own static page at `/` and its API under `/api/`, so both prefixes are
// rewritten here exactly the way nginx rewrites them in production. Sending
// these to `backend` instead yields 404s on every knowledge request.
const aiBackend = process.env.VITE_DEV_AI ?? 'http://127.0.0.1:8766'

const knowledgeProxy = {
  '^/ai-api/': {
    target: aiBackend,
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/ai-api\//, '/api/'),
  },
}

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
      ...knowledgeProxy,
      ...Object.fromEntries(apiPrefixes.map((prefix) => [prefix, backend])),
    },
  },
})
