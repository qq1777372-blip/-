<script setup lang="ts">
import { Monitor, RefreshRight, Search, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { computed, onMounted, ref, watch } from 'vue'
import { fetchSoftwareAdminUsers } from '../api'
import ListPaginationFooter from '../components/ListPaginationFooter.vue'
import { useViewport } from '../composables/useViewport'
import { useAuthStore } from '../stores/auth'
import type { SoftwareAdminUser } from '../types/api'
import { formatDateTime } from '../utils/format'

const authStore = useAuthStore()
const { isMobile, viewportHeight } = useViewport()

const loading = ref(false)
const keyword = ref('')
const statusText = ref('准备就绪')
const currentPage = ref(1)
const users = ref<SoftwareAdminUser[]>([])
const sortKey = ref<string | null>(null)
const sortOrder = ref<'ascending' | 'descending' | null>(null)

const canManageSoftwareUsers = computed(() => authStore.currentUser?.role === 'superadmin')
const pageSize = computed(() => 20)
const desktopTableHeight = computed(() => Math.max(420, viewportHeight.value - 300))
const mobileListHeight = computed(() => Math.max(420, viewportHeight.value - 260))

const activatedCount = computed(() => users.value.filter((user) => user.is_activated).length)
const inactiveCount = computed(() => users.value.filter((user) => !user.is_active).length)
const boundLicenseCount = computed(() => users.value.filter((user) => user.license_key).length)

const filteredUsers = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  if (!normalizedKeyword) {
    return users.value
  }

  return users.value.filter((user) => {
    return [
      user.username,
      user.display_name,
      user.license_key,
      user.plan_name,
      user.license_status,
    ]
      .join(' ')
      .toLowerCase()
      .includes(normalizedKeyword)
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredUsers.value.length / pageSize.value)))
const sortedUsers = computed(() => {
  if (!sortKey.value || !sortOrder.value) return filteredUsers.value
  const direction = sortOrder.value === 'ascending' ? 1 : -1
  const key = sortKey.value
  return [...filteredUsers.value].sort((left, right) => {
    const leftValue = getSoftwareUserSortValue(left, key)
    const rightValue = getSoftwareUserSortValue(right, key)
    return leftValue.localeCompare(rightValue, 'zh-CN', { numeric: true, sensitivity: 'base' }) * direction
  })
})
const paginatedUsers = computed(() => {
  const startIndex = (currentPage.value - 1) * pageSize.value
  return sortedUsers.value.slice(startIndex, startIndex + pageSize.value)
})

const statusDisplay = computed(() =>
  keyword.value.trim() ? `关键词过滤：${keyword.value.trim()}` : statusText.value,
)

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.message ?? fallback)
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return fallback
}

function getActivationTagType(user: SoftwareAdminUser) {
  if (!user.is_active) {
    return 'danger'
  }
  return user.is_activated ? 'success' : 'warning'
}

function getActivationText(user: SoftwareAdminUser) {
  if (!user.is_active) {
    return '已禁用'
  }
  return user.is_activated ? '已激活' : '未激活'
}

function formatOptionalDate(value: string | null) {
  return value ? formatDateTime(value) : '-'
}

function formatLicenseText(value: string | null) {
  return value?.trim() || '未绑定'
}

function getSoftwareUserSortValue(user: SoftwareAdminUser, key: string) {
  if (key === 'status') return user.is_active ? (user.is_activated ? '2' : '1') : '0'
  if (key === 'activation_period') return `${user.activated_at ?? ''} ${user.expire_at ?? ''}`
  if (key === 'client') return '软件'
  return String(user[key as keyof SoftwareAdminUser] ?? '')
}

function handleTableSortChange({ prop, order }: { prop: string; order: 'ascending' | 'descending' | null }) {
  sortKey.value = order ? prop : null
  sortOrder.value = order
  currentPage.value = 1
}

async function loadData(message = '正在同步软件账号...') {
  if (!canManageSoftwareUsers.value) {
    return
  }

  loading.value = true
  statusText.value = message

  try {
    const nextUsers = await fetchSoftwareAdminUsers()
    users.value = nextUsers
    statusText.value = `已加载 ${nextUsers.length} 个软件账号`
  } catch (error) {
    const messageText = getErrorMessage(error, '加载软件账号失败')
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
  () => filteredUsers.value.length,
  () => {
    if (currentPage.value > totalPages.value) {
      currentPage.value = totalPages.value
    }
  },
)

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="page-stack">
    <section v-if="!canManageSoftwareUsers" class="page-block permission-block">
      <el-result
        icon="warning"
        title="仅超级管理员可访问"
        sub-title="软件账号列表只开放给超级管理员。"
      />
    </section>

    <section v-else class="page-block list-surface list-surface--fixed software-user-surface">
      <div class="software-user-surface__section">
        <div class="filter-panel">
          <div class="query-grow">
            <div class="section-desc" style="margin-bottom: 8px">账号搜索</div>
            <el-input
              v-model="keyword"
              :prefix-icon="Search"
              clearable
              placeholder="搜索账号、卡密、套餐或状态"
              size="large"
            />
          </div>

          <div class="filter-status">
            <div class="section-desc" style="margin-bottom: 8px">系统状态</div>
            <div class="status-box" :title="statusDisplay">{{ statusDisplay }}</div>
          </div>
        </div>

        <div class="toolbar-row">
          <div>
            <h3 class="section-title" style="font-size: 16px">软件账号</h3>
            <p class="section-desc">这里显示员工在客户端注册的账号，以及卡密激活和授权校验状态。</p>
            <div class="software-user-summary" aria-label="软件账号统计">
              <span>总数 <strong>{{ users.length }}</strong></span>
              <span>已激活 <strong>{{ activatedCount }}</strong></span>
              <span>绑定卡密 <strong>{{ boundLicenseCount }}</strong></span>
              <span>已禁用 <strong>{{ inactiveCount }}</strong></span>
            </div>
          </div>
          <div class="toolbar-actions">
            <el-button :icon="RefreshRight" @click="loadData('正在手动刷新软件账号...')">刷新数据</el-button>
          </div>
        </div>

      </div>

      <div class="software-user-surface__section">
        <div v-if="isMobile" class="table-area fixed-list-shell">
          <div
            v-loading="loading"
            class="software-user-card-list fixed-list-mobile"
            :style="{ maxHeight: `${mobileListHeight}px` }"
          >
            <article v-for="user in paginatedUsers" :key="user.id" class="software-user-card">
              <div class="software-user-card__head">
                <div>
                  <h4 class="software-user-card__title">{{ user.username }}</h4>
                  <p class="software-user-card__meta">ID {{ user.id }} · {{ formatOptionalDate(user.created_at) }}</p>
                </div>
                <el-tag :type="getActivationTagType(user)" round>{{ getActivationText(user) }}</el-tag>
              </div>

              <div class="software-user-card__grid">
                <div class="software-user-card__field">
                  <span class="software-user-card__label">卡密</span>
                  <span class="software-user-card__value mono-text">{{ formatLicenseText(user.license_key) }}</span>
                </div>
                <div class="software-user-card__field">
                  <span class="software-user-card__label">套餐</span>
                  <span class="software-user-card__value">{{ user.plan_name || '-' }}</span>
                </div>
                <div class="software-user-card__field">
                  <span class="software-user-card__label">激活</span>
                  <span class="software-user-card__value">{{ formatOptionalDate(user.activated_at) }}</span>
                </div>
                <div class="software-user-card__field">
                  <span class="software-user-card__label">到期</span>
                  <span class="software-user-card__value">{{ formatOptionalDate(user.expire_at) }}</span>
                </div>
              </div>
            </article>

            <el-empty
              v-if="!paginatedUsers.length"
              :description="keyword.trim() ? '没有匹配的软件账号' : '暂无软件账号'"
            />
          </div>

          <ListPaginationFooter
            v-model:current-page="currentPage"
            :total-pages="totalPages"
            :page-size="pageSize"
            :total-items="filteredUsers.length"
          />
        </div>

        <div v-else class="table-area fixed-list-shell">
          <el-table
            v-loading="loading"
            :data="paginatedUsers"
            stripe
            :height="desktopTableHeight"
            fit
            @sort-change="handleTableSortChange"
          >
            <el-table-column prop="username" label="账号" min-width="180" fixed="left" sortable="custom">
              <template #default="{ row }">
                <div class="account-cell">
                  <el-icon><User /></el-icon>
                  <strong>{{ row.username }}</strong>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="status" label="状态" width="110" sortable="custom">
              <template #default="{ row }">
                <el-tag :type="getActivationTagType(row)" round>{{ getActivationText(row) }}</el-tag>
              </template>
            </el-table-column>

            <el-table-column prop="license_key" label="卡密" min-width="230" sortable="custom">
              <template #default="{ row }">
                <span class="mono-text">{{ formatLicenseText(row.license_key) }}</span>
              </template>
            </el-table-column>

            <el-table-column prop="plan_name" label="套餐" min-width="130" sortable="custom">
              <template #default="{ row }">{{ row.plan_name || '-' }}</template>
            </el-table-column>

            <el-table-column prop="activation_period" label="激活 / 到期" min-width="220" sortable="custom">
              <template #default="{ row }">
                <div class="info-stack">
                  <span>激活：{{ formatOptionalDate(row.activated_at) }}</span>
                  <span>到期：{{ formatOptionalDate(row.expire_at) }}</span>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="last_validated_at" label="最近校验" min-width="170" sortable="custom">
              <template #default="{ row }">{{ formatOptionalDate(row.last_validated_at) }}</template>
            </el-table-column>

            <el-table-column prop="created_at" label="注册时间" min-width="170" sortable="custom">
              <template #default="{ row }">{{ formatOptionalDate(row.created_at) }}</template>
            </el-table-column>

            <el-table-column prop="client" label="客户端" width="100" fixed="right" sortable="custom">
              <template #default>
                <el-tag type="info" round>
                  <el-icon><Monitor /></el-icon>
                  软件
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <ListPaginationFooter
            v-model:current-page="currentPage"
            :total-pages="totalPages"
            :page-size="pageSize"
            :total-items="filteredUsers.length"
          />
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.software-user-surface {
  padding: 0;
  overflow: hidden;
}

.software-user-surface__section {
  display: contents;
}

.software-user-summary {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 12px;
}

.software-user-summary span {
  white-space: nowrap;
}

.software-user-summary strong {
  margin-left: 3px;
  color: var(--text-primary);
  font-size: 13px;
}

.account-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.software-user-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: auto;
}

.software-user-card {
  padding: 14px;
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  background: #ffffff;
}

.software-user-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.software-user-card__title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-main);
}

.software-user-card__meta {
  margin: 5px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

.software-user-card__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.software-user-card__field {
  min-width: 0;
}

.software-user-card__label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
}

.software-user-card__value {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  color: var(--text-main);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
