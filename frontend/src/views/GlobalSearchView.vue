<script setup lang="ts">
import { RefreshRight, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { fetchGlobalSearch } from '../api'
import { useViewport } from '../composables/useViewport'
import type { GlobalSearchResponse, GlobalSearchResultItem } from '../types/api'

const route = useRoute()
const router = useRouter()
const { isMobile } = useViewport()

const loading = ref(false)
const keyword = ref('')
const statusText = ref('准备就绪')
const results = ref<GlobalSearchResponse | null>(null)

const sections = computed(() => {
  if (!results.value) {
    return []
  }

  return [
    { key: 'shop-records', title: '店铺台账', items: results.value.shop_records, route: '/shop-records' },
    { key: 'licenses', title: '执照档案', items: results.value.license_records, route: '/licenses' },
    { key: 'account-usage', title: '账号使用记录', items: results.value.account_usage_records, route: '/account-usage' },
    { key: 'task-bookkeeping', title: '任务记录', items: results.value.task_bookkeeping_records, route: '/task-bookkeeping/records' },
  ].filter((section) => section.items.length > 0)
})

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.message ?? fallback)
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return fallback
}

async function runSearch(queryOverride?: string) {
  const query = (queryOverride ?? keyword.value).trim()
  keyword.value = query

  await router.replace({
    query: query ? { q: query } : {},
  })

  if (!query) {
    results.value = null
    statusText.value = '请输入关键字后开始全局搜索'
    return
  }

  loading.value = true
  statusText.value = `正在搜索：${query}`

  try {
    results.value = await fetchGlobalSearch(query)
    statusText.value = `共找到 ${results.value.total} 条结果`
  } catch (error) {
    const message = getErrorMessage(error, '全局搜索失败')
    statusText.value = message
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

function resetSearch() {
  keyword.value = ''
  results.value = null
  statusText.value = '已清空搜索条件'
  void router.replace({ query: {} })
}

function resultKey(sectionKey: string, item: GlobalSearchResultItem) {
  return `${sectionKey}-${item.category}-${item.id}`
}

onMounted(() => {
  const initialQuery = typeof route.query.q === 'string' ? route.query.q.trim() : ''
  if (initialQuery) {
    void runSearch(initialQuery)
    return
  }

  statusText.value = '请输入关键字后开始全局搜索'
})
</script>

<template>
  <div class="page-stack">
    <section class="page-block list-surface list-surface--fixed">
      <div class="filter-panel">
        <div class="query-grow">
          <div class="section-desc" style="margin-bottom: 8px">全局搜索</div>
          <el-input
            v-model="keyword"
            placeholder="搜索店铺、执照主体、账号、负责人、任务备注"
            size="large"
            :prefix-icon="Search"
            clearable
            @keyup.enter="runSearch()"
          />
        </div>

        <div class="filter-status">
          <div class="section-desc" style="margin-bottom: 8px">系统状态</div>
          <div class="status-box" :title="statusText">{{ statusText }}</div>
        </div>
      </div>

      <div class="toolbar-row">
        <div>
          <h3 class="section-title" style="font-size: 16px">搜索结果</h3>
          <p class="section-desc">
            一次搜索店铺台账、执照档案、账号记录和任务记录。
          </p>
        </div>

        <div class="toolbar-actions">
          <el-button type="primary" :icon="Search" :loading="loading" @click="runSearch()">
            开始搜索
          </el-button>
          <el-button :icon="RefreshRight" :disabled="!keyword.trim()" @click="resetSearch">
            清空条件
          </el-button>
        </div>
      </div>

      <div class="global-search-shell" v-loading="loading">
        <template v-if="results">
          <div class="global-search-summary">
            匹配结果 {{ results.total }} 条
          </div>

          <el-empty v-if="!sections.length" description="暂无匹配结果" />

          <section
            v-for="section in sections"
            :key="section.key"
            class="global-search-section"
          >
            <div class="global-search-section__head">
              <h4 class="global-search-section__title">{{ section.title }}</h4>
              <RouterLink class="soft-tag" :to="section.route">打开模块</RouterLink>
            </div>

            <div class="global-search-grid">
              <article
                v-for="item in section.items"
                :key="resultKey(section.key, item)"
                class="global-search-card"
              >
                <div class="global-search-card__title">{{ item.title }}</div>
                <div v-if="item.subtitle" class="global-search-card__subtitle">{{ item.subtitle }}</div>
                <div v-if="item.detail" class="global-search-card__detail">{{ item.detail }}</div>
                <RouterLink class="global-search-card__link" :to="item.route">
                  查看模块
                </RouterLink>
              </article>
            </div>

          </section>
        </template>

        <el-empty
          v-else
          :description="isMobile ? '输入关键字后搜索' : '输入关键字后开始全局搜索'"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.global-search-shell {
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 0 22px 22px;
  min-height: 220px;
}

.global-search-summary {
  padding: 10px 0 18px;
  color: var(--text-secondary);
  font-size: 13px;
}

.global-search-section {
  display: grid;
  gap: 12px;
  padding-top: 8px;
}

.global-search-section + .global-search-section {
  margin-top: 6px;
}

.global-search-section__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.global-search-section__title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
}

.global-search-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.global-search-card {
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid #e4ebf5;
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.global-search-card__title {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.45;
  word-break: break-word;
}

.global-search-card__subtitle {
  color: var(--brand-primary);
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}

.global-search-card__detail {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.global-search-card__link {
  color: var(--brand-primary);
  font-size: 13px;
  font-weight: 600;
}

@media (max-width: 768px) {
  .global-search-shell {
    padding: 0 16px 16px;
  }
}
</style>
