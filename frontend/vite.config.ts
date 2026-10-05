import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

const apiPrefixes = ['/account-usage-records','/admin','/admin-users','/api','/article-publisher','/audit-logs','/auth','/company-expenses','/custom-fields','/dashboard','/dingtalk-profits','/expense-categories','/health','/license-admin','/license-records','/mobile-devices','/peer-shops','/reader','/saved-links','/shop-records','/software-admin','/system-alerts','/task-bookkeeping','/ui-settings','/uploads','/warehouse']

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backend = env.VITE_DEV_API ?? 'http://127.0.0.1:8000'
  const aiBackend = env.VITE_DEV_AI ?? 'http://127.0.0.1:8766'
  const directAiService = /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?/i.test(aiBackend)
  const knowledgeProxy = {
    '^/ai-api/': {
      target: aiBackend,
      changeOrigin: true,
      rewrite: (path: string) => directAiService ? path.replace(/^\/ai-api\//, '/api/') : path,
    },
  }

  return {
    base: '/ui/',
    plugins: [vue()],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    server: { port: 5173, proxy: { ...knowledgeProxy, ...Object.fromEntries(apiPrefixes.map((prefix) => [prefix, backend])) } },
  }
})
