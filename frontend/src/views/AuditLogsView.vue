<script setup lang="ts">
import { RefreshRight, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { computed, onMounted, ref, watch } from 'vue'
import { fetchAuditLogs } from '../api'
import ListPaginationFooter from '../components/ListPaginationFooter.vue'
import { useViewport } from '../composables/useViewport'
import type { AuditLog } from '../types/api'
import { formatDateTime } from '../utils/format'

const { isMobile, viewportHeight } = useViewport()

const loading = ref(false)
const keyword = ref('')
const currentPage = ref(1)
const statusText = ref('准备就绪')
const records = ref<AuditLog[]>([])
const pageSize = 20

const actionLabels: Record<string, string> = {
  login_succeeded: '登录成功',
  login_failed: '登录失败',
  login_locked: '登录已锁定',
  login_rejected_inactive: '登录被拒绝（账号禁用）',
  logout_succeeded: '退出登录',
  session_revoked: '手动下线设备',
  other_sessions_revoked: '下线其他设备',
}

const filteredRecords = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  if (!normalizedKeyword) {
    return records.value
  }

  return records.value.filter((record) =>
    [
      record.actor_username ?? '',
      record.action,
      formatAction(record.action),
      record.resource_type,
      String(record.resource_id ?? ''),
      JSON.stringify(record.details ?? {}),
    ]
      .join(' ')
      .toLowerCase()
      .includes(normalizedKeyword),
  )
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredRecords.value.length / pageSize)))

const paginatedRecords = computed(() => {
  const startIndex = (currentPage.value - 1) * pageSize
  return filteredRecords.value.slice(startIndex, startIndex + pageSize)
})

const statusDisplay = computed(() => {
  if (!keyword.value.trim()) {
    return statusText.value
  }

  return `关键词过滤：${keyword.value.trim()}`
})

const desktopTableHeight = computed(() => Math.max(420, viewportHeight.value - 360))

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.message ?? fallback)
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return fallback
}

function formatAction(action: string) {
  return actionLabels[action] ?? action
}

function formatDetails(details: Record<string, unknown>) {
  const entries = Object.entries(details ?? {})
  if (!entries.length) {
    return '-'
  }

  return entries
    .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
    .join(' | ')
}

async function loadData(message = '正在同步安全日志...') {
  loading.value = true
  statusText.value = message

  try {
    records.value = await fetchAuditLogs()
    statusText.value = `已加载 ${records.value.length} 条安全日志`
  } catch (error) {
    const messageText = getErrorMessage(error, '加载安全日志失败')
    statusText.value = messageText
    ElMessage.error(messageText)
  } finally {
    loading.value = false
  }
}

watch(keyword, () => {
  currentPage.value = 1
})

watch(
  () => filteredRecords.value.length,
  () => {
    if (currentPage.value > totalPages.value) {
      currentPage.value = totalPages.value
    }
  },
)

onMounted(loadData)
</script>

<template>
  <div class="page-stack">
    <section class="page-block list-surface">
      <div class="filter-panel">
        <div class="query-grow">
          <div class="section-desc" style="margin-bottom: 8px">关键词查询</div>
          <el-input
            v-model="keyword"
            placeholder="搜索操作人、动作、资源类型或详情"
            size="large"
            :prefix-icon="Search"
            clearable
          />
        </div>

        <div class="filter-status">
          <div class="section-desc" style="margin-bottom: 8px">系统状态</div>
          <div class="status-box" :title="statusDisplay">{{ statusDisplay }}</div>
        </div>
      </div>

      <div class="toolbar-row">
        <div>
          <h3 class="section-title" style="font-size: 16px">安全日志</h3>
          <p class="section-desc">记录敏感查看、状态变更、登录结果等关键动作，便于排查与追溯。</p>
        </div>

        <div class="toolbar-actions">
          <el-button :icon="RefreshRight" @click="loadData('正在手动刷新安全日志...')">
            刷新数据
          </el-button>
        </div>
      </div>

      <div v-if="!isMobile" class="table-area fixed-list-shell">
        <el-table :data="paginatedRecords" stripe :height="desktopTableHeight" v-loading="loading">
          <el-table-column prop="id" label="ID" width="80" fixed="left" sortable />
          <el-table-column prop="created_at" label="时间" min-width="180" sortable>
            <template #default="{ row }">
              {{ formatDateTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="actor_username" label="操作人" min-width="140" sortable />
          <el-table-column prop="action" label="动作" min-width="220" sortable>
            <template #default="{ row }">
              {{ formatAction(row.action) }}
            </template>
          </el-table-column>
          <el-table-column prop="resource_type" label="资源类型" min-width="180" sortable />
          <el-table-column prop="resource_id" label="资源 ID" min-width="100" sortable />
          <el-table-column label="详情" min-width="420" show-overflow-tooltip>
            <template #default="{ row }">
              {{ formatDetails(row.details) }}
            </template>
          </el-table-column>
        </el-table>

        <ListPaginationFooter
          v-model:current-page="currentPage"
          :total-pages="totalPages"
          :page-size="pageSize"
          :total-items="filteredRecords.length"
        />
      </div>

      <div v-else class="table-area fixed-list-shell">
        <div
          v-loading="loading"
          class="audit-card-list fixed-list-mobile"
        >
          <template v-if="filteredRecords.length">
            <article v-for="record in paginatedRecords" :key="record.id" class="audit-mobile-card">
              <div class="audit-mobile-card__head">
                <div>
                  <h4 class="audit-mobile-card__title">{{ formatAction(record.action) }}</h4>
                  <p class="audit-mobile-card__meta">
                    {{ record.actor_username || '系统' }} · {{ formatDateTime(record.created_at) }}
                  </p>
                </div>
                <span class="soft-tag">#{{ record.id }}</span>
              </div>

              <div class="audit-mobile-card__field">
                <span class="audit-mobile-card__label">资源</span>
                <span class="audit-mobile-card__value">
                  {{ record.resource_type }} / {{ record.resource_id ?? '-' }}
                </span>
              </div>

              <div class="audit-mobile-card__field">
                <span class="audit-mobile-card__label">详情</span>
                <span class="audit-mobile-card__value">{{ formatDetails(record.details) }}</span>
              </div>
            </article>
          </template>

          <el-empty
            v-else
            :description="keyword.trim() ? '没有匹配的安全日志' : '暂无安全日志'"
          />
        </div>

        <ListPaginationFooter
          v-model:current-page="currentPage"
          :total-pages="totalPages"
          :page-size="pageSize"
          :total-items="filteredRecords.length"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.audit-card-list {
  display: grid;
  gap: 12px;
  min-height: 180px;
}

.audit-mobile-card {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 10px 24px rgba(31, 41, 55, 0.06);
}

.audit-mobile-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.audit-mobile-card__title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.4;
  word-break: break-word;
}

.audit-mobile-card__meta {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.audit-mobile-card__field {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #fbfdff;
}

.audit-mobile-card__label {
  color: var(--text-secondary);
  font-size: 12px;
}

.audit-mobile-card__value {
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}
</style>
