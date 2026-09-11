import { defineConfig, loadEnv } from 'vite'
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



// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backend = env.VITE_DEV_API ?? 'http://127.0.0.1:8000'
  const aiBackend = env.VITE_DEV_AI ?? 'http://127.0.0.1:8766'
  const knowledgeProxy = {
    '^/ai-api/': {
      target: aiBackend,
      changeOrigin: true,
      rewrite: (path: string) => path.replace(/^\/ai-api\//, '/api/'),
    },
  }

  return {
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
      devOptions: { enabled: false },
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
  }
})