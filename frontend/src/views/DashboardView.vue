<script setup lang="ts">
import {
  ArrowRight,
  Box,
  CircleCloseFilled,
  Clock,
  Coin,
  CreditCard,
  DataAnalysis,
  DataLine,
  Document,
  Files,
  Finished,
  Goods,
  Management,
  Money,
  OfficeBuilding,
  Sell,
  Tickets,
  TrendCharts,
  UserFilled,
  Van,
  WarningFilled,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import {
  fetchDashboardStats,
  fetchDingTalkProfitMonthlySummary,
  fetchServerStatus,
  fetchSycmLatest,
  fetchWarehouseSummary,
} from '../api'
import { useAuthStore } from '../stores/auth'
import type {
  DashboardStats,
  DingTalkProfitMonthlySummary,
  ServerNodeStatus,
  ServerStatus,
  ServerStatusMetrics,
  SycmPeriod,
  SycmShopSnapshot,
  WarehouseSummary,
} from '../types/api'
import { formatDate, formatMoney } from '../utils/format'

const authStore = useAuthStore()
const props = withDefaults(defineProps<{ serverOnly?: boolean }>(), {
  serverOnly: false,
})
const loading = ref(false)
const stats = ref<DashboardStats | null>(null)
const warehouseSummary = ref<WarehouseSummary | null>(null)
const dingtalkMonthlyRows = ref<DingTalkProfitMonthlySummary[]>([])
const serverLoading = ref(false)
const serverStatus = ref<ServerStatus | null>(null)
// Which machine's detail is on screen. Set from the fleet once it arrives, and
// re-pointed at the first node if the selected one disappears from the config.
const activeServerNode = ref('')
const canViewServerStatus = computed(() => authStore.currentUser?.role === 'superadmin')
const canViewWarehouse = computed(() => authStore.canAccess('warehouse'))
const canViewSycm = computed(() => authStore.canAccess('shop_records'))

const sycmPeriods: { value: SycmPeriod; label: string }[] = [
  { value: 'today', label: '今日' },
  { value: 'yesterday', label: '昨日' },
  { value: 'recent7', label: '近7天' },
  { value: 'recent30', label: '近30天' },
]
const sycmPeriod = ref<SycmPeriod>('today')
const sycmLoading = ref(false)
const sycmShops = ref<SycmShopSnapshot[]>([])
const sycmFailed = ref(false)

/** 概览接口把指标放在 overview[field].value，聚合周期则直接放在顶层，两种都要兼容 */
function sycmValue(shop: SycmShopSnapshot, field: string): number | null {
  const fromOverview = shop.overview?.[field]?.value
  if (fromOverview !== undefined && fromOverview !== null) {
    return Number(fromOverview)
  }
  const fromRoot = (shop as unknown as Record<string, unknown>)[field]
  return fromRoot === undefined || fromRoot === null ? null : Number(fromRoot)
}

/** 全部店铺都没采到该指标时返回 null，避免把「未采集」显示成 0 */
function sycmSum(field: string): number | null {
  const values = sycmShops.value
    .map((shop) => sycmValue(shop, field))
    .filter((value): value is number => value !== null && Number.isFinite(value))
  return values.length ? values.reduce((total, value) => total + value, 0) : null
}

function sycmNumber(value: number | null) {
  return value === null ? '--' : new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)
}

function sycmPercent(value: number | null) {
  return value === null ? '--' : `${(value * 100).toFixed(2)}%`
}

const sycmMetrics = computed(() => {
  const uv = sycmSum('uv')
  const payByrCnt = sycmSum('payByrCnt')
  const payAmt = sycmSum('payAmt')

  return [
    { key: 'uv', label: '访客数', value: sycmNumber(uv), tone: 'indigo' },
    { key: 'pv', label: '浏览量', value: sycmNumber(sycmSum('pv')), tone: 'sky' },
    { key: 'cart', label: '加购人数', value: sycmNumber(sycmSum('cartByrCnt')), tone: 'violet' },
    { key: 'buyers', label: '支付买家', value: sycmNumber(payByrCnt), tone: 'teal' },
    {
      key: 'amount',
      label: '支付金额',
      value: payAmt === null ? '--' : `¥${sycmNumber(payAmt)}`,
      tone: 'amber',
    },
    {
      key: 'rate',
      label: '支付转化率',
      value: sycmPercent(uv && payByrCnt !== null ? payByrCnt / uv : null),
      tone: 'sky',
    },
  ]
})

/** 首页只展示前 5 名，完整榜单在生意参谋页 */
const sycmTopShops = computed(() =>
  [...sycmShops.value]
    .sort((a, b) => Number(sycmValue(b, 'payAmt') ?? 0) - Number(sycmValue(a, 'payAmt') ?? 0))
    .slice(0, 5)
    .map((shop) => {
      const uv = sycmValue(shop, 'uv')
      const buyers = sycmValue(shop, 'payByrCnt')
      const amount = sycmValue(shop, 'payAmt')
      return {
        shopId: shop.shopId,
        shopName: shop.shopName || shop.shopId,
        amount: amount === null ? '--' : `¥${sycmNumber(amount)}`,
        uv: sycmNumber(uv),
        buyers: sycmNumber(buyers),
        rate: sycmPercent(uv && buyers !== null ? buyers / uv : null),
      }
    }),
)

const sycmUpdatedAt = computed(() => {
  const latest = sycmShops.value.reduce(
    (last, shop) => (!last || (shop.collectedAt ?? '') > last ? shop.collectedAt ?? '' : last),
    '',
  )
  return latest ? formatDateTime(latest) : '暂无'
})

const overviewCards = computed(() => {
  if (!stats.value) {
    return []
  }

  return [
    {
      key: 'shop-records',
      title: '店铺台账',
      value: String(stats.value.shop_record_count),
      unit: '条',
      note: '经营主数据记录数',
      icon: Management,
      tone: 'indigo',
    },
    {
      key: 'licenses',
      title: '执照档案',
      value: String(stats.value.license_record_count),
      unit: '份',
      note: '已归档主体资料',
      icon: Document,
      tone: 'sky',
    },
    {
      key: 'fields',
      title: '自定义字段',
      value: String(stats.value.custom_field_count),
      unit: '项',
      note: '台账扩展字段数',
      icon: Tickets,
      tone: 'teal',
    },
    {
      key: 'admins',
      title: '启用管理员',
      value: String(stats.value.active_admin_count),
      unit: '人',
      note: `共 ${stats.value.admin_user_count} 个后台账号`,
      icon: UserFilled,
      tone: 'violet',
    },
    {
      key: 'deposit',
      title: '保证金总额',
      value: `¥${formatMoney(stats.value.deposit_total)}`,
      unit: '',
      note: '店铺台账保证金字段累计',
      icon: CreditCard,
      tone: 'amber',
    },
  ]
})

const reminderCards = computed(() => {
  if (!stats.value) {
    return []
  }

  const items = [
    {
      key: 'expired-license',
      title: '执照已过期',
      count: stats.value.expired_license_count,
      unit: '份',
      note: '优先处理已过期主体资料',
      to: '/licenses',
      icon: CircleCloseFilled,
      tone: 'rose',
    },
    {
      key: 'expiring-license',
      title: '30 天内到期',
      count: stats.value.expiring_license_count,
      unit: '份',
      note: '提前续证，避免店铺资料断档',
      to: '/licenses',
      icon: Clock,
      tone: 'amber',
    },
    {
      key: 'banned-account',
      title: '已封账号',
      count: stats.value.banned_account_count,
      unit: '个',
      note: '检查封禁原因和替换方案',
      to: '/account-usage',
      icon: WarningFilled,
      tone: 'rose',
    },
    {
      key: 'pending-task',
      title: '待签收任务',
      count: stats.value.pending_task_count,
      unit: '项',
      note: '及时跟进任务签收状态',
      to: '/task-bookkeeping/records',
      icon: Finished,
      tone: 'indigo',
    },
    {
      key: 'pending-settlement',
      title: '待结算任务',
      count: stats.value.pending_settlement_count,
      unit: '项',
      note: '尽快处理回款和结算',
      to: '/task-bookkeeping/records',
      icon: Money,
      tone: 'amber',
    },
  ]

  // 计数为 0 时降为静默配色，避免所有卡片同时抢注意力
  return items.map((item) => ({ ...item, tone: item.count > 0 ? item.tone : 'quiet' }))
})

const activeReminderCount = computed(() => reminderCards.value.filter((item) => item.count > 0).length)

const warehouseCards = computed(() => {
  if (!warehouseSummary.value) return []
  const summary = warehouseSummary.value

  return [
    {
      key: 'stock',
      title: '库存数量',
      value: String(summary.total_quantity),
      unit: '件',
      note: '当前全部仓库实际库存',
      to: '/warehouse/stock',
      icon: Goods,
      tone: 'indigo',
    },
    {
      key: 'outbound',
      title: '待出库',
      value: String(summary.pending_outbound_count),
      unit: '单',
      note: '尚未完成发货的出库单',
      to: '/warehouse/outbound',
      icon: Van,
      tone: summary.pending_outbound_count > 0 ? 'amber' : 'quiet',
    },
    {
      key: 'warning',
      title: '库存预警',
      value: String(summary.low_stock_count),
      unit: '项',
      note: '可用库存已达到预警值',
      to: '/warehouse/stock',
      icon: WarningFilled,
      tone: summary.low_stock_count > 0 ? 'rose' : 'quiet',
    },
    {
      key: 'today',
      title: '今日入库 / 出库',
      value: `${summary.today_inbound_quantity} / ${summary.today_outbound_quantity}`,
      unit: '件',
      note: '今日库存增减数量',
      to: '/warehouse/movements',
      icon: Sell,
      tone: summary.today_inbound_quantity + summary.today_outbound_quantity > 0 ? 'teal' : 'quiet',
    },
    {
      key: 'cost',
      title: '库存总成本',
      value: `¥${formatMoney(summary.total_cost)}`,
      unit: '',
      note: '按当前库存成本价汇总',
      to: '/warehouse/stock',
      icon: Coin,
      tone: 'violet',
    },
  ]
})

// The fleet, with the local machine first. Falls back to a single synthetic node
// so the page still renders against a backend that predates `nodes`.
const serverNodes = computed<ServerNodeStatus[]>(() => {
  const status = serverStatus.value
  if (!status) {
    return []
  }
  if (status.nodes?.length) {
    return status.nodes
  }
  return [{
    node_id: 'local',
    label: '主服务器',
    is_local: true,
    state: 'online',
    reported_at: status.generated_at,
    age_seconds: 0,
    message: null,
    metrics: status,
  }]
})

// Keep the selected tab pointing at a node that still exists: the first load has
// nothing selected, and a node dropped from SERVER_STATUS_REMOTE_NODES would
// otherwise leave the strip with no active pane.
watch(
  serverNodes,
  (nodes) => {
    if (!nodes.length) {
      activeServerNode.value = ''
      return
    }
    if (!nodes.some((node) => node.node_id === activeServerNode.value)) {
      activeServerNode.value = nodes[0].node_id
    }
  },
  { immediate: true },
)

function serverMetricCards(status: ServerStatusMetrics) {
  return [
    {
      key: 'cpu',
      title: 'CPU 使用率',
      value: status.cpu_percent === null ? '--' : `${status.cpu_percent.toFixed(1)}%`,
      note: `${status.cpu_count} 核 · 1分钟负载 ${status.load_1m ?? '--'}`,
      percent: status.cpu_percent,
      icon: DataLine,
    },
    {
      key: 'memory',
      title: '内存使用',
      value: `${status.memory_percent.toFixed(1)}%`,
      note: `${formatBytes(status.memory_used_bytes)} / ${formatBytes(status.memory_total_bytes)}`,
      percent: status.memory_percent,
      icon: DataAnalysis,
    },
    {
      key: 'disk',
      title: '磁盘使用',
      value: `${status.disk_percent.toFixed(1)}%`,
      note: `剩余 ${formatBytes(status.disk_free_bytes)} / 共 ${formatBytes(status.disk_total_bytes)}`,
      percent: status.disk_percent,
      icon: Box,
    },
    {
      key: 'database',
      title: '数据库总容量',
      value: formatBytes(status.database_total_size_bytes),
      note: `${status.database_count} 个库 · 正式库 ${formatBytes(status.active_database_total_size_bytes)}`,
      percent: null,
      icon: Files,
    },
    {
      key: 'uptime',
      title: '服务器运行时间',
      value: formatDuration(status.system_uptime_seconds),
      note: `${status.hostname} · ${status.operating_system}`,
      percent: null,
      icon: OfficeBuilding,
    },
  ]
}

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

// A node's own health only means something once it has reported; until then the
// state of the report itself is what the badge has to show.
function nodeStateLabel(node: ServerNodeStatus) {
  if (node.state === 'missing') {
    return '未上报'
  }
  if (node.state === 'stale') {
    return node.age_seconds === null ? '数据过期' : `数据过期 ${formatDuration(node.age_seconds)}`
  }
  return node.metrics ? healthLabel(node.metrics.health) : '运行正常'
}

function nodeStateTagType(node: ServerNodeStatus): 'success' | 'warning' | 'danger' | 'info' {
  if (node.state === 'missing') {
    return 'info'
  }
  if (node.state === 'stale') {
    return 'warning'
  }
  if (!node.metrics) {
    return 'info'
  }
  return node.metrics.health === 'healthy'
    ? 'success'
    : node.metrics.health === 'warning'
      ? 'warning'
      : 'danger'
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

async function loadSycm(period?: SycmPeriod) {
  if (!canViewSycm.value) {
    return
  }

  if (period) {
    sycmPeriod.value = period
  }

  sycmLoading.value = true
  try {
    sycmShops.value = await fetchSycmLatest(sycmPeriod.value)
    sycmFailed.value = false
  } catch {
    // 生意参谋是独立采集链路，加载失败不应打断工作台其余区块
    sycmShops.value = []
    sycmFailed.value = true
  } finally {
    sycmLoading.value = false
  }
}

async function loadDashboard() {
  loading.value = true

  try {
    const [dashboardStats, monthlySummary, currentWarehouseSummary] = await Promise.all([
      fetchDashboardStats(),
      fetchDingTalkProfitMonthlySummary(),
      canViewWarehouse.value ? fetchWarehouseSummary() : Promise.resolve(null),
    ])
    stats.value = dashboardStats
    dingtalkMonthlyRows.value = monthlySummary
    warehouseSummary.value = currentWarehouseSummary
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
    void loadSycm()
  }
  void loadServerStatus()
})
</script>

<template>
  <div class="page-stack">
    <el-skeleton :loading="props.serverOnly ? serverLoading : loading" animated :rows="8">
      <template #default>
        <section class="page-block dashboard-surface">
          <div v-if="!props.serverOnly && overviewCards.length" class="dash-section dash-section--kpi">
            <div class="kpi-grid">
              <article
                v-for="card in overviewCards"
                :key="card.key"
                class="kpi-card"
                :class="`tone-${card.tone}`"
              >
                <span class="kpi-card__icon">
                  <el-icon><component :is="card.icon" /></el-icon>
                </span>
                <span class="kpi-card__label">{{ card.title }}</span>
                <strong class="kpi-card__value">
                  {{ card.value }}<em v-if="card.unit">{{ card.unit }}</em>
                </strong>
                <span class="kpi-card__note">{{ card.note }}</span>
              </article>
            </div>
          </div>

          <div v-if="stats || props.serverOnly" class="dashboard-surface__scroll">
            <div v-if="!props.serverOnly && warehouseSummary" class="dash-section">
              <header class="dash-head">
                <div class="dash-head__text">
                  <h3 class="dash-head__title">仓储概览</h3>
                  <p class="dash-head__desc">库存、出库与成本的实时汇总，点击卡片进入对应模块。</p>
                </div>
                <RouterLink to="/warehouse/stock" class="dash-head__link">
                  查看库存
                  <el-icon><ArrowRight /></el-icon>
                </RouterLink>
              </header>

              <div class="tile-grid">
                <RouterLink
                  v-for="item in warehouseCards"
                  :key="item.key"
                  :to="item.to"
                  class="tile-card"
                  :class="`tone-${item.tone}`"
                >
                  <span class="tile-card__icon">
                    <el-icon><component :is="item.icon" /></el-icon>
                  </span>
                  <span class="tile-card__title">{{ item.title }}</span>
                  <strong class="tile-card__value">
                    {{ item.value }}<em v-if="item.unit">{{ item.unit }}</em>
                  </strong>
                  <span class="tile-card__note">{{ item.note }}</span>
                  <el-icon class="tile-card__arrow"><ArrowRight /></el-icon>
                </RouterLink>
              </div>
            </div>

            <div v-if="!props.serverOnly && canViewSycm" class="dash-section">
              <header class="dash-head">
                <div class="dash-head__text">
                  <h3 class="dash-head__title">生意参谋</h3>
                  <p class="dash-head__desc">
                    多店铺经营数据汇总，数据更新：{{ sycmUpdatedAt }}
                  </p>
                </div>
                <div class="dash-head__actions">
                  <div class="period-switch">
                    <button
                      v-for="item in sycmPeriods"
                      :key="item.value"
                      type="button"
                      class="period-switch__item"
                      :class="{ 'is-active': sycmPeriod === item.value }"
                      :disabled="sycmLoading"
                      @click="loadSycm(item.value)"
                    >
                      {{ item.label }}
                    </button>
                  </div>
                  <RouterLink to="/sycm" class="dash-head__link">
                    查看详情
                    <el-icon><ArrowRight /></el-icon>
                  </RouterLink>
                </div>
              </header>

              <div v-loading="sycmLoading" class="sycm-block">
                <div class="metric-strip">
                  <div
                    v-for="item in sycmMetrics"
                    :key="item.key"
                    class="metric-strip__item"
                    :class="`tone-${item.tone}`"
                  >
                    <span class="metric-strip__label">{{ item.label }}</span>
                    <strong class="metric-strip__value">{{ item.value }}</strong>
                  </div>
                </div>

                <div v-if="sycmTopShops.length" class="data-panel">
                  <div class="data-panel__head">
                    <div>
                      <h4>店铺经营表现</h4>
                      <p>按支付金额排序，最多显示前 5 家</p>
                    </div>
                    <span class="dash-badge">
                      <el-icon class="dash-badge__icon"><TrendCharts /></el-icon>
                      共 {{ sycmShops.length }} 家店铺
                    </span>
                  </div>
                  <el-table :data="sycmTopShops" stripe class="summary-table">
                    <el-table-column prop="shopName" label="店铺" min-width="160" show-overflow-tooltip />
                    <el-table-column prop="amount" label="支付金额" min-width="130" align="right">
                      <template #default="{ row }">
                        <span class="amount-cell">{{ row.amount }}</span>
                      </template>
                    </el-table-column>
                    <el-table-column prop="uv" label="访客数" min-width="100" align="right" />
                    <el-table-column prop="buyers" label="支付买家" min-width="110" align="right" />
                    <el-table-column prop="rate" label="转化率" min-width="100" align="right" />
                  </el-table>
                </div>

                <el-empty
                  v-else-if="!sycmLoading"
                  :description="sycmFailed ? '生意参谋数据暂时无法加载' : '当前周期暂无采集数据'"
                />
              </div>
            </div>

            <div v-if="!props.serverOnly" class="dash-section">
              <header class="dash-head">
                <div class="dash-head__text">
                  <h3 class="dash-head__title">待办提醒中心</h3>
                  <p class="dash-head__desc">
                    <template v-if="activeReminderCount">
                      当前共有 {{ activeReminderCount }} 项提醒有待处理，点击卡片可直接进入对应模块。
                    </template>
                    <template v-else>暂无待处理提醒，各项指标均在正常范围内。</template>
                  </p>
                </div>
                <span class="dash-badge" :class="activeReminderCount ? 'dash-badge--alert' : 'dash-badge--ok'">
                  {{ activeReminderCount ? `${activeReminderCount} 项待处理` : '全部正常' }}
                </span>
              </header>

              <div class="tile-grid">
                <RouterLink
                  v-for="item in reminderCards"
                  :key="item.key"
                  :to="item.to"
                  class="tile-card"
                  :class="`tone-${item.tone}`"
                >
                  <span class="tile-card__icon">
                    <el-icon><component :is="item.icon" /></el-icon>
                  </span>
                  <span class="tile-card__title">{{ item.title }}</span>
                  <strong class="tile-card__value">
                    {{ item.count }}<em>{{ item.unit }}</em>
                  </strong>
                  <span class="tile-card__note">{{ item.note }}</span>
                  <el-icon class="tile-card__arrow"><ArrowRight /></el-icon>
                </RouterLink>
              </div>
            </div>

            <div v-if="canViewServerStatus && props.serverOnly" class="dash-section">
              <section v-loading="serverLoading" class="server-shell">
                <header class="dash-head">
                  <div class="dash-head__text">
                    <h3 class="dash-head__title">服务器运行状态</h3>
                    <p class="dash-head__desc">
                      查看服务器资源、后台服务以及全部 SQLite 数据库容量，仅超级管理员可见。
                    </p>
                  </div>
                  <div class="dash-head__actions">
                    <el-tag
                      v-if="serverStatus"
                      :type="serverStatus.health === 'healthy' ? 'success' : serverStatus.health === 'warning' ? 'warning' : 'danger'"
                      effect="light"
                      round
                    >
                      {{ healthLabel(serverStatus.health) }}
                    </el-tag>
                    <el-button :loading="serverLoading" @click="loadServerStatus(true, true)">
                      刷新状态
                    </el-button>
                  </div>
                </header>

                <!-- One tab per machine rather than stacking every machine's
                     metrics and two tables down the page: the tab strip is the
                     fleet overview (each label carries its own health dot), and
                     only the selected machine's detail is rendered. -->
                <el-tabs v-if="serverNodes.length" v-model="activeServerNode" class="server-tabs">
                  <el-tab-pane
                    v-for="node in serverNodes"
                    :key="node.node_id"
                    :name="node.node_id"
                  >
                    <template #label>
                      <span class="server-tab__label">
                        <span class="server-tab__dot" :class="`is-${nodeStateTagType(node)}`" />
                        {{ node.label }}
                        <span v-if="node.is_local" class="server-tab__badge">本机</span>
                      </span>
                    </template>

                    <header class="server-node__head">
                      <div class="server-node__title">
                        <el-tag :type="nodeStateTagType(node)" size="small" round>
                          {{ nodeStateLabel(node) }}
                        </el-tag>
                        <span v-if="node.metrics" class="server-node__host">
                          {{ node.metrics.hostname }} · {{ node.metrics.operating_system }}
                        </span>
                      </div>
                    </header>

                    <p v-if="node.message" class="server-node__message">{{ node.message }}</p>

                    <template v-if="node.metrics">
                      <!-- label/value pairs rather than pill chips: the values are
                           what matters here, and the chips made a header row read
                           as five unrelated buttons. -->
                      <dl class="server-meta">
                        <div class="server-meta__item">
                          <dt>架构</dt>
                          <dd>{{ node.metrics.architecture }}</dd>
                        </div>
                        <div class="server-meta__item">
                          <dt>进程 PID</dt>
                          <dd>{{ node.metrics.process_id }}</dd>
                        </div>
                        <div class="server-meta__item">
                          <dt>应用运行</dt>
                          <dd>{{ formatDuration(node.metrics.process_uptime_seconds) }}</dd>
                        </div>
                        <div class="server-meta__item">
                          <dt>采集时间</dt>
                          <dd>{{ formatDateTime(node.metrics.generated_at) }}</dd>
                        </div>
                        <div v-if="!node.is_local" class="server-meta__item">
                          <dt>上报时间</dt>
                          <dd>{{ node.reported_at ? formatDateTime(node.reported_at) : '--' }}</dd>
                        </div>
                      </dl>

                      <div class="tile-grid server-metric-grid">
                        <article
                          v-for="card in serverMetricCards(node.metrics)"
                          :key="card.key"
                          class="tile-card tile-card--static tone-indigo"
                        >
                          <span class="tile-card__icon">
                            <el-icon><component :is="card.icon" /></el-icon>
                          </span>
                          <span class="tile-card__title">{{ card.title }}</span>
                          <strong class="tile-card__value">{{ card.value }}</strong>
                          <el-progress
                            v-if="card.percent !== null"
                            :percentage="Math.round(card.percent)"
                            :stroke-width="6"
                            :show-text="false"
                            :status="card.percent >= 90 ? 'exception' : card.percent >= 75 ? 'warning' : 'success'"
                          />
                          <span class="tile-card__note">{{ card.note }}</span>
                        </article>
                      </div>

                      <!-- Stacked rather than two columns: four services next to a
                           long database table left the services column padded out
                           with empty space no matter how the heights were aligned.
                           A handful of services reads better as a row of chips. -->
                      <div class="server-panels">
                        <section class="data-panel">
                          <div class="data-panel__head">
                            <div>
                              <h4>服务状态</h4>
                              <p>系统服务实时运行情况</p>
                            </div>
                            <span class="dash-badge dash-badge--ok">
                              {{ node.metrics.services.filter((item) => item.is_active).length }} / {{ node.metrics.services.length }} 正常
                            </span>
                          </div>
                          <div class="service-chips">
                            <article
                              v-for="service in node.metrics.services"
                              :key="service.name"
                              class="service-chip"
                            >
                              <span class="service-chip__dot" :class="`is-${statusTagType(service.active_state)}`" />
                              <span class="service-chip__body">
                                <strong>{{ service.display_name || service.name }}</strong>
                                <small>{{ serviceStatusLabel(service.active_state) }} · {{ service.sub_state }}</small>
                              </span>
                            </article>
                            <p v-if="!node.metrics.services.length" class="service-chips__empty">
                              暂无服务状态数据
                            </p>
                          </div>
                        </section>

                        <section class="data-panel data-panel--database">
                          <div class="data-panel__head">
                            <div>
                              <h4>数据库容量</h4>
                              <p>
                                正式库 {{ formatBytes(node.metrics.active_database_total_size_bytes) }}，
                                备份库 {{ formatBytes(node.metrics.backup_database_total_size_bytes) }}
                              </p>
                            </div>
                            <el-tag :type="statusTagType(node.metrics.database_connection_status)" size="small" round>
                              <template v-if="node.metrics.database_connection_status === 'not-configured'">
                                无应用数据库
                              </template>
                              <template v-else>
                                主库 {{ node.metrics.database_connection_status === 'available' ? '连接正常' : '连接异常' }}
                                <template v-if="node.metrics.database_latency_ms !== null">
                                  · {{ node.metrics.database_latency_ms }} ms
                                </template>
                              </template>
                            </el-tag>
                          </div>
                          <el-table :data="node.metrics.databases" stripe max-height="420">
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
                                <el-tag :type="row.category === 'active' ? 'primary' : 'info'" size="small" round>
                                  {{ row.category === 'active' ? '正式库' : '备份库' }}
                                </el-tag>
                              </template>
                            </el-table-column>
                            <el-table-column prop="status" label="状态" width="90" sortable>
                              <template #default="{ row }">
                                <el-tag :type="statusTagType(row.status)" size="small" round>
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

                    <el-empty v-else :description="`${node.label} 暂无上报数据`" :image-size="72" />
                  </el-tab-pane>
                </el-tabs>

                <el-empty v-else description="暂无服务器状态数据" />
              </section>
            </div>

            <div v-if="!props.serverOnly" class="dash-section">
              <header class="dash-head">
                <div class="dash-head__text">
                  <h3 class="dash-head__title">钉钉利润月度统计</h3>
                  <p class="dash-head__desc">
                    按月份查看钉钉机器人同步到网站的利润统计，不再放在利润页面单独展示。
                  </p>
                </div>
                <span class="dash-badge">{{ dingtalkMonthlyRows.length }} 个月</span>
              </header>

              <el-table
                v-if="dingtalkMonthlyRows.length"
                :data="dingtalkMonthlyRows"
                stripe
                class="summary-table"
              >
                <el-table-column prop="month" label="月份" min-width="110" sortable />
                <el-table-column prop="total_profit" label="总利润" min-width="140" align="right" sortable>
                  <template #default="{ row }">
                    <span class="amount-cell">¥ {{ formatMoney(row.total_profit) }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="record_count" label="记录数" min-width="100" align="right" sortable />
                <el-table-column prop="store_count" label="店铺数" min-width="100" align="right" sortable />
                <el-table-column prop="reporter_count" label="录入人数" min-width="110" align="right" sortable />
                <el-table-column prop="latest_report_date" label="最近报表日" min-width="130" sortable>
                  <template #default="{ row }">{{ formatDate(row.latest_report_date) }}</template>
                </el-table-column>
              </el-table>

              <el-empty v-else description="暂无钉钉利润月度数据" />
            </div>
          </div>
        </section>
      </template>
    </el-skeleton>
  </div>
</template>

<style scoped>
/* ---------- 色板：每个 tone 只定义一次，图标/数字/描边共用 ---------- */
.tone-indigo {
  --tone: #6366f1;
  --tone-ink: #4f46e5;
  --tone-soft: rgba(99, 102, 241, 0.11);
  --tone-line: rgba(99, 102, 241, 0.26);
}

.tone-sky {
  --tone: #0ea5e9;
  --tone-ink: #0284c7;
  --tone-soft: rgba(14, 165, 233, 0.11);
  --tone-line: rgba(14, 165, 233, 0.26);
}

.tone-teal {
  --tone: #10b981;
  --tone-ink: #059669;
  --tone-soft: rgba(16, 185, 129, 0.12);
  --tone-line: rgba(16, 185, 129, 0.26);
}

.tone-violet {
  --tone: #8b5cf6;
  --tone-ink: #7c3aed;
  --tone-soft: rgba(139, 92, 246, 0.11);
  --tone-line: rgba(139, 92, 246, 0.26);
}

.tone-amber {
  --tone: #f59e0b;
  --tone-ink: #b45309;
  --tone-soft: rgba(245, 158, 11, 0.13);
  --tone-line: rgba(245, 158, 11, 0.3);
}

.tone-rose {
  --tone: #ef4444;
  --tone-ink: #dc2626;
  --tone-soft: rgba(239, 68, 68, 0.11);
  --tone-line: rgba(239, 68, 68, 0.26);
}

/* 计数为 0 的卡片保持安静，让真正需要处理的项目突出 */
.tone-quiet {
  --tone: #9ca3af;
  --tone-ink: #9ca3af;
  --tone-soft: rgba(156, 163, 175, 0.14);
  --tone-line: #e5e7eb;
}

/* ---------- 外层容器 ---------- */
.dashboard-surface {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: calc(100vh - 104px);
  max-height: calc(100vh - 104px);
}

.dashboard-surface__scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.dashboard-surface__scroll::-webkit-scrollbar {
  width: 8px;
}

.dashboard-surface__scroll::-webkit-scrollbar-thumb {
  border: 2px solid transparent;
  border-radius: 999px;
  background: #d8dbe2;
  background-clip: content-box;
}

.dashboard-surface__scroll::-webkit-scrollbar-thumb:hover {
  background: #c2c7d0;
  background-clip: content-box;
}

/* 区块之间只用发丝线分隔，避免卡片套卡片的多重描边 */
.dash-section {
  min-width: 0;
  padding: 20px 22px;
}

.dash-section + .dash-section,
.dashboard-surface__scroll > .dash-section:first-child {
  border-top: 1px solid var(--panel-border);
}

.dash-section--kpi {
  flex: 0 0 auto;
  padding-bottom: 20px;
  background: linear-gradient(180deg, #fbfcfe 0%, #ffffff 100%);
}

/* ---------- 区块标题 ---------- */
.dash-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.dash-head__text {
  position: relative;
  min-width: 0;
  padding-left: 12px;
}

.dash-head__text::before {
  content: '';
  position: absolute;
  top: 3px;
  left: 0;
  width: 3px;
  height: 17px;
  border-radius: 999px;
  background: var(--brand-primary);
}

.dash-head__title {
  margin: 0;
  color: var(--text-main);
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.2px;
}

.dash-head__desc {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 12.5px;
  line-height: 1.6;
}

.dash-head__actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dash-head__link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  padding: 5px 10px;
  border-radius: 999px;
  color: var(--brand-primary);
  font-size: 12.5px;
  font-weight: 600;
  transition: background-color 0.16s ease, gap 0.16s ease;
}

.dash-head__link:hover {
  gap: 7px;
  background: rgba(99, 102, 241, 0.1);
}

.dash-badge {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  height: 26px;
  padding: 0 11px;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: #f9fafb;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.dash-badge--alert {
  border-color: rgba(245, 158, 11, 0.34);
  background: rgba(245, 158, 11, 0.11);
  color: #b45309;
}

.dash-badge--ok {
  border-color: rgba(16, 185, 129, 0.3);
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.dash-badge__icon {
  margin-right: 4px;
}

/* ---------- 生意参谋概览 ---------- */
.sycm-block {
  display: grid;
  gap: 14px;
  min-height: 120px;
}

.period-switch {
  display: inline-flex;
  align-items: center;
  padding: 3px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f6f7f9;
}

.period-switch__item {
  min-width: 48px;
  height: 28px;
  padding: 0 10px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  transition: color 0.16s ease, background-color 0.16s ease, box-shadow 0.16s ease;
}

.period-switch__item:hover:not(:disabled) {
  color: var(--brand-primary);
}

.period-switch__item.is-active {
  background: #ffffff;
  color: var(--brand-primary);
  font-weight: 700;
  box-shadow: 0 1px 4px rgba(17, 24, 39, 0.12);
}

.period-switch__item:disabled {
  cursor: wait;
  opacity: 0.65;
}

.metric-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  overflow: hidden;
  border: 1px solid #e8eaee;
  border-radius: var(--panel-radius);
  background: #ffffff;
}

.metric-strip__item {
  position: relative;
  display: grid;
  gap: 7px;
  min-width: 0;
  padding: 15px 16px;
}

.metric-strip__item + .metric-strip__item {
  border-left: 1px solid #eef0f3;
}

.metric-strip__item::before {
  content: '';
  position: absolute;
  top: 14px;
  left: 0;
  width: 2px;
  height: 28px;
  border-radius: 999px;
  background: var(--tone);
  opacity: 0;
}

.metric-strip__item:hover::before {
  opacity: 1;
}

.metric-strip__label {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 12px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.metric-strip__value {
  overflow: hidden;
  color: var(--tone-ink);
  font-size: 21px;
  font-weight: 700;
  line-height: 1.25;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* ---------- 顶部核心指标 ---------- */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(198px, 1fr));
  gap: 14px;
  min-width: 0;
}

.kpi-card {
  position: relative;
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  grid-template-areas:
    'icon label'
    'icon value'
    'note note';
  align-items: center;
  gap: 2px 12px;
  overflow: hidden;
  min-width: 0;
  padding: 16px 18px;
  border: 1px solid #e8eaee;
  border-radius: var(--panel-radius);
  background: #ffffff;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.kpi-card::after {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: var(--tone);
  opacity: 0;
  transition: opacity 0.18s ease;
}

.kpi-card:hover {
  transform: translateY(-2px);
  border-color: var(--tone-line);
  box-shadow: 0 10px 24px -14px rgba(17, 24, 39, 0.28);
}

.kpi-card:hover::after {
  opacity: 1;
}

.kpi-card__icon {
  grid-area: icon;
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: var(--tone-soft);
  color: var(--tone-ink);
  font-size: 19px;
}

.kpi-card__label {
  grid-area: label;
  align-self: end;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 12.5px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.kpi-card__value {
  grid-area: value;
  align-self: start;
  overflow: hidden;
  color: var(--text-main);
  font-size: 25px;
  font-weight: 700;
  line-height: 1.24;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.kpi-card__value em {
  margin-left: 3px;
  color: var(--text-secondary);
  font-size: 12.5px;
  font-style: normal;
  font-weight: 600;
}

.kpi-card__note {
  grid-area: note;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #eef0f3;
  color: #98a1ae;
  font-size: 11.5px;
  line-height: 1.5;
}

/* ---------- 通用数据磁贴（仓储 / 待办 / 服务器指标） ---------- */
.tile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(196px, 1fr));
  grid-auto-rows: 1fr;
  gap: 12px;
  min-width: 0;
}

.tile-card {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-areas:
    'title icon'
    'value icon'
    'note note';
  align-content: start;
  gap: 4px 10px;
  overflow: hidden;
  min-width: 0;
  padding: 15px 16px;
  border: 1px solid #e8eaee;
  border-radius: var(--panel-radius);
  background: #ffffff;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease, background-color 0.18s ease;
}

.tile-card:not(.tile-card--static):hover {
  transform: translateY(-2px);
  border-color: var(--tone-line);
  background: linear-gradient(180deg, #ffffff 0%, var(--tone-soft) 340%);
  box-shadow: 0 12px 26px -16px rgba(17, 24, 39, 0.3);
}

.tile-card__icon {
  grid-area: icon;
  align-self: start;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: var(--tone-soft);
  color: var(--tone-ink);
  font-size: 16px;
}

.tile-card__title {
  grid-area: title;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 12.5px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.tile-card__value {
  grid-area: value;
  overflow: hidden;
  color: var(--tone-ink);
  font-size: 27px;
  font-weight: 700;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.tile-card__value em {
  margin-left: 3px;
  color: var(--text-secondary);
  font-size: 12.5px;
  font-style: normal;
  font-weight: 600;
}

.tile-card__note {
  grid-area: note;
  margin-top: 9px;
  padding-top: 9px;
  border-top: 1px dashed #eef0f3;
  color: #98a1ae;
  font-size: 11.5px;
  line-height: 1.5;
}

.tile-card__arrow {
  position: absolute;
  right: 14px;
  bottom: 13px;
  color: var(--tone);
  font-size: 13px;
  opacity: 0;
  transform: translateX(-4px);
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.tile-card:hover .tile-card__arrow {
  opacity: 1;
  transform: translateX(0);
}

.tile-card :deep(.el-progress) {
  grid-column: 1 / -1;
  margin-top: 8px;
}

/* ---------- 服务器状态 ---------- */
.server-shell {
  min-width: 0;
}

/* The tab strip doubles as the fleet overview, so the dot has to read at a
   glance -- it is the only health signal for the machines not currently open. */
.server-tabs {
  min-width: 0;
}

.server-tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}

.server-tabs :deep(.el-tabs__item) {
  height: 38px;
  font-weight: 500;
}

.server-tab__label {
  display: inline-flex;
  gap: 7px;
  align-items: center;
}

.server-tab__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--el-color-info, #909399);
}

.server-tab__dot.is-success {
  background: var(--el-color-success, #67c23a);
}

.server-tab__dot.is-warning {
  background: var(--el-color-warning, #e6a23c);
}

.server-tab__dot.is-danger {
  background: var(--el-color-danger, #f56c6c);
}

.server-tab__badge {
  padding: 1px 6px;
  border-radius: 5px;
  background: var(--fill-soft, #f0f2f5);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 400;
}

.server-node__head {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.server-node__title {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  min-width: 0;
}

.server-node__title h4 {
  margin: 0;
  font-size: 15px;
}

.server-node__host {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 12px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.server-node__message {
  margin: 8px 0 0;
  padding: 8px 11px;
  border-radius: 9px;
  background: var(--fill-soft, #f4f7fb);
  color: var(--text-secondary);
  font-size: 12px;
}

.server-node__empty {
  padding: 18px 0 4px;
}

.server-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 28px;
  margin: 12px 0 16px;
  padding: 11px 14px;
  border: 1px solid var(--border-soft, #eef0f4);
  border-radius: 10px;
  background: #fbfcfd;
}

.server-meta__item {
  display: flex;
  gap: 8px;
  align-items: baseline;
  min-width: 0;
}

.server-meta dt {
  color: var(--text-secondary);
  font-size: 11.5px;
  white-space: nowrap;
}

.server-meta dd {
  margin: 0;
  color: var(--text-primary, #1f2937);
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
}

.server-metric-grid {
  margin-bottom: 16px;
}

/* Full-width rows instead of side-by-side columns: the services panel is always
   a few rows tall while the database table scrolls to 420px, so any shared row
   left one column padded out with dead space. Stacking also removes the old
   834px minimum that used to force the page into a horizontal scroll. */
.server-panels {
  display: grid;
  gap: 14px;
  min-width: 0;
}

.service-chips {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 10px;
}

.service-chip {
  display: flex;
  gap: 9px;
  align-items: center;
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid var(--border-soft, #eef0f4);
  border-radius: 10px;
  background: #fbfcfd;
}

.service-chip__dot {
  flex: none;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--el-color-info, #909399);
}

.service-chip__dot.is-success {
  background: var(--el-color-success, #67c23a);
}

.service-chip__dot.is-warning {
  background: var(--el-color-warning, #e6a23c);
}

.service-chip__dot.is-danger {
  background: var(--el-color-danger, #f56c6c);
}

.service-chip__body {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.service-chip__body strong {
  overflow: hidden;
  color: var(--text-primary, #1f2937);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.service-chip__body small {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 11.5px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.service-chips__empty {
  margin: 0;
  padding: 6px 0 2px;
  color: var(--text-secondary);
  font-size: 12px;
}

.data-panel {
  min-width: 0;
  overflow: hidden;
  padding: 16px;
  border: 1px solid #e8eaee;
  border-radius: var(--panel-radius);
  background: #ffffff;
}

.data-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.data-panel__head h4,
.data-panel__head p {
  margin: 0;
}

.data-panel__head h4 {
  margin-bottom: 4px;
  font-size: 14px;
  font-weight: 700;
}

.data-panel__head p {
  color: var(--text-secondary);
  font-size: 11.5px;
  line-height: 1.5;
}

.database-name-cell {
  display: grid;
  gap: 3px;
  line-height: 1.4;
}

.database-name-cell span {
  color: var(--text-secondary);
  font-size: 11.5px;
  word-break: break-all;
}

/* ---------- 表格 ---------- */
.summary-table {
  width: 100%;
}

.amount-cell {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.dash-section :deep(.el-table th.el-table__cell) {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.2px;
}

.dash-section :deep(.el-table) {
  --el-table-border-color: #f1f2f5;
}

/* ---------- 响应式 ---------- */
@media (max-width: 1180px) {
  .metric-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .metric-strip__item:nth-child(4) {
    border-left: 0;
  }

  .metric-strip__item:nth-child(n + 4) {
    border-top: 1px solid #eef0f3;
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

  .dash-section {
    padding: 16px;
  }

  .dash-section--kpi {
    padding-bottom: 14px;
  }

  .kpi-grid,
  .tile-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .kpi-card,
  .tile-card {
    padding: 13px 14px;
  }

  .kpi-card {
    grid-template-columns: 32px minmax(0, 1fr);
  }

  .kpi-card__icon {
    width: 32px;
    height: 32px;
    border-radius: 9px;
    font-size: 16px;
  }

  .kpi-card__value,
  .tile-card__value {
    font-size: 21px;
  }

  .kpi-card__note,
  .tile-card__note {
    margin-top: 8px;
    padding-top: 8px;
  }

  .dash-head__actions {
    width: 100%;
    justify-content: space-between;
  }

  .period-switch {
    flex: 1;
  }

  .period-switch__item {
    flex: 1;
    min-width: 0;
    padding: 0 5px;
  }

  .metric-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .metric-strip__item:nth-child(4) {
    border-left: 1px solid #eef0f3;
  }

  .metric-strip__item:nth-child(odd) {
    border-left: 0;
  }

  .metric-strip__item:nth-child(n + 3) {
    border-top: 1px solid #eef0f3;
  }

  .metric-strip__value {
    font-size: 19px;
  }

  .data-panel {
    padding: 12px;
  }
}

@media (max-width: 480px) {
  .kpi-grid,
  .tile-grid {
    grid-template-columns: 1fr;
  }
}
</style>
