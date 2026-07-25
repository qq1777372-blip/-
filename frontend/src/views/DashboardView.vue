<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { fetchDashboardStats, fetchDingTalkProfitMonthlySummary, fetchServerStatus } from '../api'
import { useAuthStore } from '../stores/auth'
import type { DashboardStats, DingTalkProfitMonthlySummary, ServerStatus } from '../types/api'
import { formatDate, formatMoney } from '../utils/format'

const authStore = useAuthStore()
const props = withDefaults(defineProps<{ serverOnly?: boolean }>(), {
  serverOnly: false,
})
const loading = ref(false)
const stats = ref<DashboardStats | null>(null)
const dingtalkMonthlyRows = ref<DingTalkProfitMonthlySummary[]>([])
const serverLoading = ref(false)
const serverStatus = ref<ServerStatus | null>(null)
const canViewServerStatus = computed(() => authStore.currentUser?.role === 'superadmin')

const overviewCards = computed(() => {
  if (!stats.value) {
    return []
  }

  return [
    {
      key: 'shop-records',
      title: '店铺台账',
      value: String(stats.value.shop_record_count),
      note: '经营主数据记录数',
      tone: 'default',
    },
    {
      key: 'licenses',
      title: '执照档案',
      value: String(stats.value.license_record_count),
      note: '已归档主体资料',
      tone: 'default',
    },
    {
      key: 'fields',
      title: '自定义字段',
      value: String(stats.value.custom_field_count),
      note: '台账扩展字段数',
      tone: 'default',
    },
    {
      key: 'admins',
      title: '启用管理员',
      value: String(stats.value.active_admin_count),
      note: `共 ${stats.value.admin_user_count} 个后台账号`,
      tone: 'default',
    },
    {
      key: 'deposit',
      title: '保证金总额',
      value: `¥ ${formatMoney(stats.value.deposit_total)}`,
      note: '店铺台账保证金字段累计',
      tone: 'accent',
    },
  ]
})

const reminderCards = computed(() => {
  if (!stats.value) {
    return []
  }

  return [
    {
      key: 'expired-license',
      title: '执照已过期',
      count: stats.value.expired_license_count,
      note: '优先处理已过期主体资料',
      to: '/licenses',
      tone: 'danger',
    },
    {
      key: 'expiring-license',
      title: '30天内到期',
      count: stats.value.expiring_license_count,
      note: '提前续证，避免店铺资料断档',
      to: '/licenses',
      tone: 'warning',
    },
    {
      key: 'banned-account',
      title: '已封账号',
      count: stats.value.banned_account_count,
      note: '检查封禁原因和替换方案',
      to: '/account-usage',
      tone: 'danger',
    },
    {
      key: 'pending-task',
      title: '待签收任务',
      count: stats.value.pending_task_count,
      note: '及时跟进任务签收状态',
      to: '/task-bookkeeping/records',
      tone: 'primary',
    },
    {
      key: 'pending-settlement',
      title: '待结算任务',
      count: stats.value.pending_settlement_count,
      note: '尽快处理回款和结算',
      to: '/task-bookkeeping/records',
      tone: 'warning',
    },
  ]
})

const activeReminderCount = computed(() => reminderCards.value.filter((item) => item.count > 0).length)

const serverMetricCards = computed(() => {
  if (!serverStatus.value) {
    return []
  }

  const status = serverStatus.value
  return [
    {
      key: 'cpu',
      title: 'CPU 使用率',
      value: status.cpu_percent === null ? '--' : `${status.cpu_percent.toFixed(1)}%`,
      note: `${status.cpu_count} 核 · 1分钟负载 ${status.load_1m ?? '--'}`,
      percent: status.cpu_percent,
    },
    {
      key: 'memory',
      title: '内存使用',
      value: `${status.memory_percent.toFixed(1)}%`,
      note: `${formatBytes(status.memory_used_bytes)} / ${formatBytes(status.memory_total_bytes)}`,
      percent: status.memory_percent,
    },
    {
      key: 'disk',
      title: '磁盘使用',
      value: `${status.disk_percent.toFixed(1)}%`,
      note: `剩余 ${formatBytes(status.disk_free_bytes)} / 共 ${formatBytes(status.disk_total_bytes)}`,
      percent: status.disk_percent,
    },
    {
      key: 'database',
      title: '数据库总容量',
      value: formatBytes(status.database_total_size_bytes),
      note: `${status.database_count} 个库 · 正式库 ${formatBytes(status.active_database_total_size_bytes)}`,
      percent: null,
    },
    {
      key: 'uptime',
      title: '服务器运行时间',
      value: formatDuration(status.system_uptime_seconds),
      note: `${status.hostname} · ${status.operating_system}`,
      percent: null,
    },
  ]
})

function formatBytes(value: number) {
  if (!Number.isFinite(value) || value <= 0) {
    return '0 B'
  }

  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1)
  const scaled = value / 1024 ** index
  return `${scaled.toFixed(index === 0 || scaled >= 100 ? 0 : 1)} ${units[index]}`
}

function formatDuration(value: number | null) {
  if (value === null || value < 0) {
    return '--'
  }

  const days = Math.floor(value / 86400)
  const hours = Math.floor((value % 86400) / 3600)
  const minutes = Math.floor((value % 3600) / 60)
  if (days > 0) {
    return `${days}天 ${hours}小时`
  }
  if (hours > 0) {
    return `${hours}小时 ${minutes}分钟`
  }
  return `${minutes}分钟`
}

function formatDateTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString('zh-CN', { hour12: false })
}

function serviceStatusLabel(activeState: string) {
  const labels: Record<string, string> = {
    active: '运行中',
    inactive: '已停止',
    failed: '故障',
    activating: '启动中',
    deactivating: '停止中',
    unavailable: '不可读取',
    'not-found': '未安装',
  }
  return labels[activeState] ?? activeState
}

function databaseStatusLabel(status: string) {
  if (status === 'available') {
    return '可读取'
  }
  if (status === 'restricted') {
    return '权限受限'
  }
  return '异常'
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'active' || status === 'available') {
    return 'success'
  }
  if (status === 'failed' || status === 'error') {
    return 'danger'
  }
  if (status === 'inactive' || status === 'activating' || status === 'deactivating') {
    return 'warning'
  }
  return 'info'
}

function healthLabel(health: ServerStatus['health']) {
  return health === 'healthy' ? '运行正常' : health === 'warning' ? '需要关注' : '存在故障'
}

async function loadServerStatus(refresh = false, showMessage = false) {
  if (!canViewServerStatus.value) {
    return
  }

  serverLoading.value = true
  try {
    serverStatus.value = await fetchServerStatus(refresh)
    if (showMessage) {
      ElMessage.success('服务器状态已刷新')
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '加载服务器状态失败'
    if (showMessage) {
      ElMessage.error(message)
    }
  } finally {
    serverLoading.value = false
  }
}

async function loadDashboard() {
  loading.value = true

  try {
    const [dashboardStats, monthlySummary] = await Promise.all([
      fetchDashboardStats(),
      fetchDingTalkProfitMonthlySummary(),
    ])
    stats.value = dashboardStats
    dingtalkMonthlyRows.value = monthlySummary
  } catch (error) {
    const message = error instanceof Error ? error.message : '加载运营工作台失败'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (!props.serverOnly) {
    void loadDashboard()
  }
  void loadServerStatus()
})
</script>

<template>
  <div class="page-stack">
    <el-skeleton :loading="props.serverOnly ? serverLoading : loading" animated :rows="8">
      <template #default>
        <section class="page-block dashboard-surface">
          <div v-if="!props.serverOnly && overviewCards.length" class="dashboard-surface__section dashboard-surface__section--metrics">
            <div class="metric-grid">
              <article
                v-for="card in overviewCards"
                :key="card.key"
                class="metric-card dashboard-metric-card dashboard-inner-card"
                :class="`dashboard-metric-card--${card.tone}`"
              >
                <div class="metric-label">{{ card.title }}</div>
                <div class="metric-value">{{ card.value }}</div>
                <div class="metric-note">{{ card.note }}</div>
              </article>
            </div>
          </div>

          <div v-if="stats || props.serverOnly" class="dashboard-surface__scroll">
            <div v-if="!props.serverOnly" class="dashboard-surface__section">
              <section class="reminder-shell">
                <div class="reminder-head">
                  <div>
                    <h3 class="section-title">待办提醒中心</h3>
                    <p class="section-desc">
                      当前共有 {{ activeReminderCount }} 项提醒有待处理，点击卡片可直接进入对应模块。
                    </p>
                  </div>
                  <span class="reminder-head__badge">{{ activeReminderCount }} 项</span>
                </div>

                <div class="reminder-grid">
                  <RouterLink
                    v-for="item in reminderCards"
                    :key="item.key"
                    :to="item.to"
                    class="reminder-card"
                    :class="`reminder-card--${item.tone}`"
                  >
                    <span class="reminder-card__title">{{ item.title }}</span>
                    <strong class="reminder-card__value">{{ item.count }}</strong>
                    <span class="reminder-card__note">{{ item.note }}</span>
                  </RouterLink>
                </div>
              </section>
            </div>

            <div v-if="canViewServerStatus && props.serverOnly" class="dashboard-surface__section">
              <section v-loading="serverLoading" class="server-shell">
                <div class="server-head">
                  <div>
                    <h3 class="section-title">服务器运行状态</h3>
                    <p class="section-desc">
                      查看服务器资源、后台服务以及全部 SQLite 数据库容量，仅超级管理员可见。
                    </p>
                  </div>
                  <div class="server-head__actions">
                    <el-tag
                      v-if="serverStatus"
                      :type="serverStatus.health === 'healthy' ? 'success' : serverStatus.health === 'warning' ? 'warning' : 'danger'"
                      effect="light"
                    >
                      {{ healthLabel(serverStatus.health) }}
                    </el-tag>
                    <el-button :loading="serverLoading" @click="loadServerStatus(true, true)">
                      刷新状态
                    </el-button>
                  </div>
                </div>

                <template v-if="serverStatus">
                  <div class="server-meta">
                    <span>架构：{{ serverStatus.architecture }}</span>
                    <span>进程 PID：{{ serverStatus.process_id }}</span>
                    <span>应用运行：{{ formatDuration(serverStatus.process_uptime_seconds) }}</span>
                    <span>采集时间：{{ formatDateTime(serverStatus.generated_at) }}</span>
                  </div>

                  <div class="server-metric-grid">
                    <article v-for="card in serverMetricCards" :key="card.key" class="server-metric-card">
                      <span>{{ card.title }}</span>
                      <strong>{{ card.value }}</strong>
                      <el-progress
                        v-if="card.percent !== null"
                        :percentage="Math.round(card.percent)"
                        :stroke-width="7"
                        :show-text="false"
                        :status="card.percent >= 90 ? 'exception' : card.percent >= 75 ? 'warning' : 'success'"
                      />
                      <small>{{ card.note }}</small>
                    </article>
                  </div>

                  <div class="server-list-grid">
                    <section class="server-list-panel">
                      <div class="server-list-title">
                        <div>
                          <h4>服务状态</h4>
                          <p>系统服务实时运行情况</p>
                        </div>
                        <span>{{ serverStatus.services.filter((item) => item.is_active).length }} / {{ serverStatus.services.length }} 正常</span>
                      </div>
                      <el-table :data="serverStatus.services" stripe>
                        <el-table-column prop="display_name" label="服务" min-width="130" sortable />
                        <el-table-column prop="active_state" label="状态" width="100" sortable>
                          <template #default="{ row }">
                            <el-tag :type="statusTagType(row.active_state)" size="small">
                              {{ serviceStatusLabel(row.active_state) }}
                            </el-tag>
                          </template>
                        </el-table-column>
                        <el-table-column prop="sub_state" label="运行阶段" min-width="100" sortable />
                      </el-table>
                    </section>

                    <section class="server-list-panel server-list-panel--database">
                      <div class="server-list-title">
                        <div>
                          <h4>数据库容量</h4>
                          <p>
                            正式库 {{ formatBytes(serverStatus.active_database_total_size_bytes) }}，
                            备份库 {{ formatBytes(serverStatus.backup_database_total_size_bytes) }}
                          </p>
                        </div>
                        <el-tag :type="statusTagType(serverStatus.database_connection_status)" size="small">
                          主库 {{ serverStatus.database_connection_status === 'available' ? '连接正常' : '连接异常' }}
                          <template v-if="serverStatus.database_latency_ms !== null">
                            · {{ serverStatus.database_latency_ms }} ms
                          </template>
                        </el-tag>
                      </div>
                      <el-table :data="serverStatus.databases" stripe max-height="420">
                        <el-table-column prop="name" label="数据库" min-width="220" sortable>
                          <template #default="{ row }">
                            <div class="database-name-cell">
                              <strong>{{ row.name }}</strong>
                              <span>{{ row.source }} · {{ row.relative_path }}</span>
                            </div>
                          </template>
                        </el-table-column>
                        <el-table-column prop="category" label="类型" width="90" sortable>
                          <template #default="{ row }">
                            <el-tag :type="row.category === 'active' ? 'primary' : 'info'" size="small">
                              {{ row.category === 'active' ? '正式库' : '备份库' }}
                            </el-tag>
                          </template>
                        </el-table-column>
                        <el-table-column prop="status" label="状态" width="90" sortable>
                          <template #default="{ row }">
                            <el-tag :type="statusTagType(row.status)" size="small">
                              {{ databaseStatusLabel(row.status) }}
                            </el-tag>
                          </template>
                        </el-table-column>
                        <el-table-column prop="size_bytes" label="容量" width="110" align="right" sortable>
                          <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
                        </el-table-column>
                        <el-table-column prop="modified_at" label="更新时间" min-width="165" sortable>
                          <template #default="{ row }">{{ formatDateTime(row.modified_at) }}</template>
                        </el-table-column>
                      </el-table>
                    </section>
                  </div>
                </template>

                <el-empty v-else description="暂无服务器状态数据" />
              </section>
            </div>

            <div v-if="!props.serverOnly" class="dashboard-surface__section">
              <section class="summary-shell">
                <div class="summary-head">
                  <div>
                    <h3 class="section-title">钉钉利润月度统计</h3>
                    <p class="section-desc">
                      按月份查看钉钉机器人同步到网站的利润统计，不再放在利润页面单独展示。
                    </p>
                  </div>
                  <span class="reminder-head__badge">{{ dingtalkMonthlyRows.length }} 个月</span>
                </div>

                <el-table
                  v-if="dingtalkMonthlyRows.length"
                  :data="dingtalkMonthlyRows"
                  stripe
                  class="summary-table"
                >
                  <el-table-column prop="month" label="月份" min-width="110" sortable />
                  <el-table-column prop="total_profit" label="总利润" min-width="140" sortable>
                    <template #default="{ row }">¥ {{ formatMoney(row.total_profit) }}</template>
                  </el-table-column>
                  <el-table-column prop="record_count" label="记录数" min-width="100" sortable />
                  <el-table-column prop="store_count" label="店铺数" min-width="100" sortable />
                  <el-table-column prop="reporter_count" label="录入人数" min-width="110" sortable />
                  <el-table-column prop="latest_report_date" label="最近报表日" min-width="130" sortable>
                    <template #default="{ row }">{{ formatDate(row.latest_report_date) }}</template>
                  </el-table-column>
                </el-table>

                <el-empty v-else description="暂无钉钉利润月度数据" />
              </section>
            </div>
          </div>
        </section>
      </template>
    </el-skeleton>
  </div>
</template>

<style scoped>
.dashboard-surface {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: calc(100vh - 104px);
  max-height: calc(100vh - 104px);
}

.dashboard-surface__section {
  min-width: 0;
  padding: 22px;
}

.dashboard-surface__section + .dashboard-surface__section {
  border-top: 1px solid var(--panel-border);
}

.dashboard-surface__section--metrics {
  flex: 0 0 auto;
  padding-bottom: 18px;
}

.dashboard-surface__scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.dashboard-inner-card {
  box-shadow: none;
}

.dashboard-metric-card {
  border: 1px solid #dfe7f3;
  border-radius: var(--panel-radius);
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
}

.dashboard-metric-card--accent {
  border-color: #cfe0ff;
  background: linear-gradient(180deg, #ffffff 0%, #f3f8ff 100%);
}

.dashboard-metric-card--accent .metric-value {
  color: var(--brand-primary);
}

.reminder-shell,
.summary-shell,
.server-shell {
  padding: 20px 22px 22px;
  border: 1px solid #e6edf7;
  border-radius: var(--panel-radius);
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
}

.reminder-head,
.summary-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.reminder-head__badge {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  background: #eef4ff;
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 700;
}

.reminder-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  grid-auto-rows: 1fr;
  gap: 12px;
}

.reminder-card {
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 10px;
  min-height: var(--uniform-card-min-height);
  height: 100%;
  padding: 18px;
  border: 1px solid #dbe6f5;
  border-radius: var(--panel-radius);
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

.reminder-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 28px rgba(31, 41, 55, 0.08);
}

.reminder-card__title {
  color: var(--text-secondary);
  font-size: 13px;
}

.reminder-card__value {
  font-size: 30px;
  line-height: 1;
}

.reminder-card__note {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.reminder-card--danger {
  border-color: #ffd5d5;
}

.reminder-card--danger .reminder-card__value {
  color: #d14343;
}

.reminder-card--warning {
  border-color: #ffe2b8;
}

.reminder-card--warning .reminder-card__value {
  color: #c47a10;
}

.reminder-card--primary {
  border-color: #cfe0ff;
}

.reminder-card--primary .reminder-card__value {
  color: var(--brand-primary);
}

.summary-table {
  width: 100%;
}

.server-head,
.server-list-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.server-head {
  margin-bottom: 14px;
}

.server-head__actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.server-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  margin-bottom: 16px;
  color: var(--text-secondary);
  font-size: 12px;
}

.server-metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.server-metric-card {
  display: grid;
  gap: 9px;
  padding: 16px;
  border: 1px solid #dfe7f3;
  border-radius: 14px;
  background: #fbfdff;
}

.server-metric-card > span,
.server-metric-card > small,
.server-list-title p,
.database-name-cell span {
  color: var(--text-secondary);
}

.server-metric-card > span {
  font-size: 13px;
}

.server-metric-card > strong {
  font-size: 24px;
  line-height: 1.1;
}

.server-metric-card > small {
  line-height: 1.5;
}

.server-list-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.8fr) minmax(560px, 1.6fr);
  gap: 14px;
}

.server-list-panel {
  min-width: 0;
  overflow: hidden;
  padding: 16px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #ffffff;
}

.server-list-title {
  margin-bottom: 12px;
}

.server-list-title h4,
.server-list-title p {
  margin: 0;
}

.server-list-title h4 {
  margin-bottom: 4px;
  font-size: 15px;
}

.server-list-title p,
.server-list-title > span {
  font-size: 12px;
}

.database-name-cell {
  display: grid;
  gap: 3px;
  line-height: 1.4;
}

.database-name-cell span {
  font-size: 12px;
  word-break: break-all;
}

@media (max-width: 1180px) {
  .server-list-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .dashboard-surface {
    height: auto;
    max-height: none;
  }

  .dashboard-surface__scroll {
    overflow: visible;
  }

  .dashboard-surface__section {
    padding: 16px;
  }

  .dashboard-surface__section--metrics {
    padding-bottom: 12px;
  }

  .reminder-shell,
  .summary-shell,
  .server-shell {
    padding: 16px;
  }

  .reminder-card {
    min-height: var(--uniform-card-min-height-mobile);
    padding: 16px;
  }

  .server-head__actions {
    width: 100%;
    justify-content: space-between;
  }

  .server-metric-grid {
    grid-template-columns: 1fr 1fr;
  }

  .server-list-panel {
    padding: 12px;
  }
}

@media (max-width: 520px) {
  .server-metric-grid {
    grid-template-columns: 1fr;
  }
}
</style>
