import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

// Every backend prefix the App calls. Listed explicitly rather than proxying `/`
// so the dev server keeps serving its own assets and HMR. Some list pages build
// their endpoint dynamically (`/${resource}`), so a new module may need its
// prefix added here even though nothing else changed.
const apiPrefixes = [
  '/account-usage-records',
  '/admin',
  '/admin-users',
  '/api',
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
  '/saved-links',
  '/shop-records',
  '/software-admin',
  '/system-alerts',
  '/system-settings',
  '/task-bookkeeping',
  '/ui-settings',
  '/uploads',
  '/warehouse',
]

const backend = process.env.VITE_DEV_API ?? 'http://127.0.0.1:8000'

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
export default defineConfig(({ mode }) => ({
  base: mode === 'native' ? './' : '/app/',
  server: {
    port: 5174,
    proxy: {
      ...knowledgeProxy,
      ...Object.fromEntries(apiPrefixes.map((prefix) => [prefix, backend])),
    },
  },
  plugins: [
    vue(),
    VitePWA({
      registerType: 'prompt',
      injectRegister: null,
      includeAssets: ['favicon.svg', 'icons.svg'],
      manifest: {
        name: '小许后台管理系统',
        short_name: '小许后台',
        description: '店铺、任务、记账、库存与利润管理',
        lang: 'zh-CN',
        start_url: '/app/',
        scope: '/app/',
        display: 'standalone',
        background_color: '#f5f7fb',
        theme_color: '#1677ff',
        icons: [
          { src: '/app/favicon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' },
        ],
      },
      workbox: {
        cleanupOutdatedCaches: true,
        navigateFallback: '/app/index.html',
        navigateFallbackDenylist: [/^\/auth\//, /^\/api\//, /^\/internal\//],
        globPatterns: ['**/*.{js,css,html,svg,woff2,png,jpg,jpeg,webp}'],
        // No runtimeCaching entry on purpose: API/auth/attachment responses are
        // never copied to Cache Storage. Only Vite's generated static assets are
        // precached, and financial writes are always network-only.
        runtimeCaching: [],
      },
    }),
  ],
  build: { outDir: '../app-frontend-dist', emptyOutDir: true },
}))
