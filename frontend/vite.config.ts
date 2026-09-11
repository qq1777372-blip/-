import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backend = 'https://xiaoxu666.asia'
const aiBackend = 'https://xiaoxu666.asia'
const apiPrefixes = ['/account-usage-records','/admin','/admin-users','/api','/article-publisher','/audit-logs','/auth','/company-expenses','/custom-fields','/dashboard','/dingtalk-profits','/expense-categories','/health','/license-admin','/license-records','/mobile-devices','/peer-shops','/reader','/saved-links','/shop-records','/software-admin','/system-alerts','/task-bookkeeping','/ui-settings','/uploads','/warehouse']
const knowledgeProxy = { '^/ai-api/': { target: aiBackend, changeOrigin: true, rewrite: (path: string) => path } }

export default defineConfig({
  base: '/ui/',
  plugins: [vue()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: { port: 5173, proxy: { ...knowledgeProxy, ...Object.fromEntries(apiPrefixes.map((prefix) => [prefix, backend])) } }
})