<script setup lang="ts">
import {
  Cellphone,
  Coin,
  DataAnalysis,
  Document,
  Refresh,
  Sell,
  ShoppingCart,
  TrendCharts,
  UserFilled,
  View,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  createSycmSyncRequest,
  fetchSycmCollectorDevices,
  fetchSycmLatest,
  fetchSycmLatestSyncRequest,
} from '../api'
import type {
  SycmCollectorDevice,
  SycmPeriod,
  SycmSessionState,
  SycmShopSnapshot,
  SycmSyncRequest,
} from '../types/api'

type ViewKey = 'overview' | 'sources' | 'details' | 'status'

const periods: { value: SycmPeriod; label: string }[] = [
  { value: 'today', label: '今日' },
  { value: 'yesterday', label: '昨日' },
  { value: 'recent7', label: '近7天' },
  { value: 'recent30', label: '近30天' },
]

const views: { value: ViewKey; label: string }[] = [
  { value: 'overview', label: '店铺概览' },
  { value: 'sources', label: '流量来源' },
  { value: 'details', label: '详细指标' },
  { value: 'status', label: '同步状态' },
]

const period = ref<SycmPeriod>('today')
const activeView = ref<ViewKey>('overview')
const selectedShop = ref('')
const loading = ref(false)
const syncing = ref(false)
const errorMessage = ref('')
const shops = ref<SycmShopSnapshot[]>([])
const devices = ref<SycmCollectorDevice[]>([])
const syncTask = ref<SycmSyncRequest | null>(null)
const overviewPage = ref(1)
const sourcePage = ref(1)

// 每页行数由表格区实测高度算出，不写死。写死过 20（配 max-height 内部滚动，13 家店
// 把整页顶出视口）和 8（换个屏幕高度还是溢出）。这里量的是 flex 分给表格区的真实
// 像素，所以 KPI 从 6 列掉到 2 列、筛选栏在 900px 以下堆成三行之类的重排都会自动
// 反映进来，不需要在每个断点重算一遍偏移量。
const OVERVIEW_ROW_H = 50 // 店铺单元格是两行（店名 + ID）
const SOURCE_ROW_H = 44 // 来源单元格是单行
const TABLE_HEAD_H = 40

const tableAreaRef = ref<HTMLElement | null>(null)
const tableAreaHeight = ref(0)
let areaObserver: ResizeObserver | null = null

function rowsThatFit(rowHeight: number) {
  const body = tableAreaHeight.value - TABLE_HEAD_H
  // 量到 0 时（首帧、或切到无表格的页签）给 8，避免这一帧渲染 0 行闪一下空表
  if (body <= 0) return 8
  return Math.max(3, Math.floor(body / rowHeight))
}

const overviewPageSize = computed(() => rowsThatFit(OVERVIEW_ROW_H))
const sourcePageSize = computed(() => rowsThatFit(SOURCE_ROW_H))

// 同步轮询用，组件卸载时必须清掉，否则会在已销毁组件上继续写状态
let syncCancelled = false
let syncTimer: ReturnType<typeof setTimeout> | null = null

const numberFormatter = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 })

function formatNumber(value: number | null) {
  return value === null ? '--' : numberFormatter.format(value)
}

function formatMoney(value: number | null) {
  return value === null ? '--' : `¥${numberFormatter.format(value)}`
}

function formatPercent(value: number | null) {
  return value === null ? '--' : `${(value * 100).toFixed(2)}%`
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return '暂无'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '暂无' : date.toLocaleString('zh-CN', { hour12: false })
}

/** 概览接口把指标放在 overview[field].value，聚合周期直接放顶层，两种都要兼容 */
function metricOf(shop: SycmShopSnapshot, field: string): number | null {
  const fromOverview = shop.overview?.[field]?.value
  if (fromOverview !== undefined && fromOverview !== null) {
    return Number(fromOverview)
  }
  const raw = (shop as unknown as Record<string, unknown>)[field]
  if (raw === undefined || raw === null) return null
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
}

/** 全部店铺都没采到该指标时返回 null，避免把「未采集」显示成 0 */
function sumMetric(list: SycmShopSnapshot[], field: string): number | null {
  const values = list
    .map((shop) => metricOf(shop, field))
    .filter((value): value is number => value !== null)
  return values.length ? values.reduce((total, value) => total + value, 0) : null
}

const visibleShops = computed(() =>
  selectedShop.value ? shops.value.filter((shop) => shop.shopId === selectedShop.value) : shops.value,
)

const failedShopIds = computed(() => new Set(
  (syncTask.value?.status === 'completed' ? syncTask.value.results : [])
    .filter((result) => result.success === false && result.shopId)
    .map((result) => String(result.shopId)),
))

const currentShops = computed(() => visibleShops.value.filter((shop) => !failedShopIds.value.has(shop.shopId)))

const kpiCards = computed(() => {
  const list = currentShops.value
  const uv = sumMetric(list, 'uv')
  const buyers = sumMetric(list, 'payByrCnt')
  const amount = sumMetric(list, 'payAmt')
  const cart = sumMetric(list, 'cartByrCnt')

  return [
    { key: 'uv', label: '访客数', value: formatNumber(uv), note: '覆盖店铺访问用户', icon: View, tone: 'indigo' },
    { key: 'pv', label: '浏览量', value: formatNumber(sumMetric(list, 'pv')), note: '页面浏览总量', icon: Document, tone: 'sky' },
    {
      key: 'cart',
      label: '加购人数',
      value: formatNumber(cart),
      note: cart === null ? '当前周期暂无该指标' : '产生加购的用户',
      icon: ShoppingCart,
      tone: 'violet',
    },
    { key: 'buyers', label: '支付买家', value: formatNumber(buyers), note: '完成支付的用户', icon: UserFilled, tone: 'teal' },
    { key: 'amount', label: '支付金额', value: formatMoney(amount), note: '成交支付金额', icon: Coin, tone: 'amber' },
    {
      key: 'rate',
      label: '支付转化率',
      value: formatPercent(uv && buyers !== null ? buyers / uv : null),
      note: '支付买家 / 访客',
      icon: TrendCharts,
      tone: 'sky',
    },
  ]
})

const overviewRows = computed(() =>
  [...visibleShops.value]
    .sort((a, b) => Number(metricOf(b, 'payAmt') ?? 0) - Number(metricOf(a, 'payAmt') ?? 0))
    .map((shop, index) => {
      const uv = metricOf(shop, 'uv')
      const buyers = metricOf(shop, 'payByrCnt')
      const amount = metricOf(shop, 'payAmt')
      return {
        rank: index + 1,
        shopId: shop.shopId,
        shopName: shop.shopName || shop.shopId,
        sessionFailed: failedShopIds.value.has(shop.shopId),
        amount: formatMoney(amount),
        uv: formatNumber(uv),
        buyers: formatNumber(buyers),
        rate: formatPercent(uv && buyers !== null ? buyers / uv : null),
        avgPrice: formatMoney(buyers && amount !== null ? amount / buyers : null),
      }
    }),
)

const paginatedOverviewRows = computed(() => {
  const start = (overviewPage.value - 1) * overviewPageSize.value
  return overviewRows.value.slice(start, start + overviewPageSize.value)
})

// 切换周期 / 店铺筛选时重置页码
function resetPages() {
  overviewPage.value = 1
  sourcePage.value = 1
}

// 店铺下拉是 v-model 直接改的，不走 load()，所以筛选后也要把页码拉回第一页，
// 否则筛出 1 家店时还停在第 2 页会看到空表格。
watch(selectedShop, resetPages)

// 表格区在 v-if 分支里，切页签是换了一个 DOM 节点，得重新挂观察器
watch(activeView, async () => {
  await nextTick()
  observeTableArea()
})


function observeTableArea() {
  areaObserver?.disconnect()
  const el = tableAreaRef.value
  if (!el) {
    tableAreaHeight.value = 0
    return
  }
  tableAreaHeight.value = el.clientHeight
  areaObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      tableAreaHeight.value = entry.contentRect.height
    }
  })
  areaObserver.observe(el)
}

const sourceRows = computed(() => {
  // 只有今日快照带来源明细，历史周期后端不返回 sourceTree
  if (period.value !== 'today') return []
  const merged = new Map<string, { name: string; uv: number; buyers: number; amount: number }>()

  currentShops.value.forEach((shop) => {
    const tree = Array.isArray(shop.sourceTree) ? shop.sourceTree : []
    tree.forEach((node) => {
      const source = node as Record<string, { value?: unknown } | undefined>
      const name = String(source?.pageName?.value ?? '') || '其他来源'
      const current = merged.get(name) ?? { name, uv: 0, buyers: 0, amount: 0 }
      current.uv += Number(source?.uv?.value ?? 0)
      current.buyers += Number(source?.payByrCnt?.value ?? 0)
      current.amount += Number(source?.payAmt?.value ?? 0)
      merged.set(name, current)
    })
  })

  return [...merged.values()]
    .sort((a, b) => b.uv - a.uv)
    .map((item) => ({
      name: item.name,
      uv: formatNumber(item.uv),
      buyers: formatNumber(item.buyers),
      amount: formatMoney(item.amount),
      rate: formatPercent(item.uv ? item.buyers / item.uv : null),
    }))
})

const paginatedSourceRows = computed(() => {
  const start = (sourcePage.value - 1) * sourcePageSize.value
  return sourceRows.value.slice(start, start + sourcePageSize.value)
})

// 窗口变矮 -> 每页行数变少 -> 总页数变少，当前页可能落到范围外，会显示空表格。
// 必须放在两个 rows computed 之后：watch 的 getter 是立即执行的，声明提前会 TDZ 报错。
watch([overviewPageSize, () => overviewRows.value.length], () => {
  const totalPages = Math.max(1, Math.ceil(overviewRows.value.length / overviewPageSize.value))
  if (overviewPage.value > totalPages) overviewPage.value = totalPages
})

watch([sourcePageSize, () => sourceRows.value.length], () => {
  const totalPages = Math.max(1, Math.ceil(sourceRows.value.length / sourcePageSize.value))
  if (sourcePage.value > totalPages) sourcePage.value = totalPages
})

const detailDefinitions: { field: string; label: string; type: 'number' | 'money' | 'percent' }[] = [
  { field: 'itmUv', label: '商品访客', type: 'number' },
  { field: 'itmPv', label: '商品浏览', type: 'number' },
  { field: 'newUv', label: '新访客', type: 'number' },
  { field: 'oldUv', label: '老访客', type: 'number' },
  { field: 'cltCnt', label: '收藏次数', type: 'number' },
  { field: 'shopCltByrCnt', label: '店铺收藏人数', type: 'number' },
  { field: 'itmCltByrCnt', label: '商品收藏人数', type: 'number' },
  { field: 'crtByrCnt', label: '下单买家', type: 'number' },
  { field: 'payOrdCnt', label: '支付订单', type: 'number' },
  { field: 'uvValue', label: '访客价值', type: 'money' },
  { field: 'payPct', label: '客单价', type: 'money' },
  { field: 'crtRate', label: '下单转化率', type: 'percent' },
]

const detailCards = computed(() =>
  detailDefinitions
    .map((item) => ({ ...item, raw: sumMetric(currentShops.value, item.field) }))
    .filter((item) => item.raw !== null)
    .map((item) => ({
      field: item.field,
      label: item.label,
      value:
        item.type === 'money'
          ? formatMoney(item.raw)
          : item.type === 'percent'
            ? formatPercent(item.raw)
            : formatNumber(item.raw),
    })),
)

const onlineDeviceCount = computed(() => devices.value.filter((device) => device.online).length)
// Distinct from the count above: a device can be connected yet unable to read
// Qianniu, and that is the number that decides whether a sync can produce data.
const collectableDeviceCount = computed(() => devices.value.filter((device) => device.collectable).length)

function sessionLabel(state: SycmSessionState) {
  return state === 'ready' ? '可采集' : state === 'blocked' ? '无法采集' : '状态未知'
}

function sessionTagType(state: SycmSessionState): 'success' | 'warning' | 'info' {
  return state === 'ready' ? 'success' : state === 'blocked' ? 'warning' : 'info'
}

// The agent sends its own tally (locked / logged_out / empty / no_permission).
// Passing it through beats a generic "check your login", which was misleading
// whenever the real cause was Qianniu locking the cookie DB.
function deviceSessionHint(device: SycmCollectorDevice) {
  if (device.sessionDetail) {
    return device.sessionDetail
  }
  return device.sessionState === 'blocked'
    ? '千牛会话不可用，采集会拿不到数据'
    : '采集端未上报会话状态'
}

const updatedAt = computed(() => {
  const latest = visibleShops.value.reduce(
    (last, shop) => (!last || (shop.collectedAt ?? '') > last ? shop.collectedAt ?? '' : last),
    '',
  )
  return formatDateTime(latest)
})

const contextLabel = computed(() => {
  const label = periods.find((item) => item.value === period.value)?.label ?? '今日'
  return `${label} · ${selectedShop.value ? '单店' : `${shops.value.length} 家店铺`}`
})

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    shops.value = await fetchSycmLatest(period.value)
    if (selectedShop.value && !shops.value.some((shop) => shop.shopId === selectedShop.value)) {
      selectedShop.value = ''
    }
    resetPages()
    // 任务与设备是辅助信息，失败不应让整页变成错误态
    const [task, deviceList] = await Promise.all([
      fetchSycmLatestSyncRequest().catch(() => syncTask.value),
      fetchSycmCollectorDevices().catch(() => devices.value),
    ])
    syncTask.value = task ?? null
    devices.value = deviceList ?? []
  } catch (error) {
    shops.value = []
    errorMessage.value = error instanceof Error ? error.message : '生意参谋数据加载失败'
  } finally {
    loading.value = false
  }
}

async function changePeriod(value: SycmPeriod) {
  if (period.value === value || loading.value) return
  period.value = value
  await load()
}

function waitFor(ms: number) {
  return new Promise<void>((resolve) => {
    syncTimer = setTimeout(() => {
      syncTimer = null
      resolve()
    }, ms)
  })
}

async function startSync() {
  if (syncing.value) return
  syncing.value = true
  syncCancelled = false

  try {
    // 没有在线采集端时，任务会一直停在 pending —— 谁也不会来领它，按钮只能空转
    // 到 3 分钟超时。先取一次最新设备状态再决定：与其让用户干等，不如立刻说明
    // 原因。用最新结果而不是 devices.value，避免拿到进页面时的旧快照。
    const latestDevices = await fetchSycmCollectorDevices().catch(() => devices.value)
    devices.value = latestDevices ?? []
    if (!devices.value.some((device) => device.online)) {
      ElMessage.warning('没有已连接的采集设备，同步任务无人认领。请先启动采集端程序。')
      return
    }
    // 只在采集端明确说自己被挡住时才拦。此前的条件是「没有一台 collectable」，
    // 而 collectable 要求 sessionState 恰为 ready —— 于是 unknown（旧版采集端、
    // 或刚重启还没报过状态）也会被当成故障拦下，明明能采却发不出任务。
    const blocked = devices.value.find((device) => device.online && device.sessionState === 'blocked')
    if (blocked && !devices.value.some((device) => device.collectable)) {
      ElMessage.warning(
        blocked.sessionDetail
          ? `采集端已连接，但拿不到千牛会话：${blocked.sessionDetail}`
          : '采集端已连接，但拿不到千牛会话，同步会采不到数据。千牛运行时会锁定 Cookie 库，需要先关闭千牛。',
      )
      return
    }

    const task = await createSycmSyncRequest()
    syncTask.value = task

    for (let attempt = 0; attempt < 45; attempt += 1) {
      if (syncCancelled) return
      const current = await fetchSycmLatestSyncRequest()
      if (syncCancelled) return
      syncTask.value = current ?? null

      if (current?.id === task.id && current.status === 'completed') {
        await load()
        if (!syncCancelled) {
          activeView.value = 'status'
          ElMessage.success('同步完成')
        }
        return
      }
      if (current?.id === task.id && current.status === 'failed') {
        throw new Error(current.error || '采集端同步失败')
      }
      await waitFor(2000)
    }
    if (!syncCancelled) {
      ElMessage.warning('同步确认超时，按钮已恢复。请检查采集器状态后重试')
    }
  } catch (error) {
    if (!syncCancelled) {
      ElMessage.error(error instanceof Error ? error.message : '同步失败')
    }
  } finally {
    syncing.value = false
  }
}

onMounted(() => {
  observeTableArea()
  void load()
})

onBeforeUnmount(() => {
  // 离开页面时终止轮询，避免定时器在组件销毁后继续回写状态
  syncCancelled = true
  if (syncTimer !== null) {
    clearTimeout(syncTimer)
    syncTimer = null
  }
  areaObserver?.disconnect()
  areaObserver = null
})
</script>

<template>
  <div class="sycm-page">
    <header class="sycm-top">
      <div class="sycm-title">
        <h2>生意参谋</h2>
        <p>多店铺经营数据工作台</p>
      </div>
      <div class="sycm-actions">
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" :icon="DataAnalysis" :loading="syncing" @click="startSync">
          {{ syncing ? '同步中...' : '同步数据' }}
        </el-button>
      </div>
    </header>

    <section class="page-block sycm-controlbar">
      <label class="sycm-field">
        <span class="sycm-field__label">店铺范围</span>
        <el-select v-model="selectedShop" filterable clearable placeholder="全部店铺">
          <el-option :label="`全部店铺（${shops.length}）`" value="" />
          <el-option
            v-for="shop in shops"
            :key="shop.shopId"
            :label="shop.shopName || shop.shopId"
            :value="shop.shopId"
          />
        </el-select>
      </label>

      <div class="sycm-field">
        <span id="sycm-period-label" class="sycm-field__label">数据周期</span>
        <div class="sycm-segments" role="group" aria-labelledby="sycm-period-label">
          <button
            v-for="item in periods"
            :key="item.value"
            type="button"
            class="sycm-segment"
            :class="{ 'is-active': period === item.value }"
            :disabled="loading"
            :aria-pressed="period === item.value"
            @click="changePeriod(item.value)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>

      <div class="sycm-freshness">
        数据更新 <strong>{{ updatedAt }}</strong>
      </div>
    </section>

    <el-alert v-if="errorMessage" type="error" :title="errorMessage" :closable="false" show-icon />

    <section v-loading="loading" class="page-block sycm-kpis">
      <article v-for="card in kpiCards" :key="card.key" class="sycm-kpi" :class="`tone-${card.tone}`">
        <span class="sycm-kpi__icon">
          <el-icon><component :is="card.icon" /></el-icon>
        </span>
        <span class="sycm-kpi__label">{{ card.label }}</span>
        <strong class="sycm-kpi__value">{{ card.value }}</strong>
        <span class="sycm-kpi__note">{{ card.note }}</span>
      </article>
    </section>

    <nav class="page-block sycm-nav">
      <div class="sycm-tabs" role="tablist" aria-label="生意参谋视图">
        <button
          v-for="item in views"
          :id="`sycm-tab-${item.value}`"
          :key="item.value"
          type="button"
          role="tab"
          class="sycm-tab"
          :class="{ 'is-active': activeView === item.value }"
          :aria-selected="activeView === item.value"
          :aria-controls="`sycm-panel-${item.value}`"
          @click="activeView = item.value"
        >
          {{ item.label }}
        </button>
      </div>
      <span class="sycm-context">{{ contextLabel }}</span>
    </nav>

    <section
      v-if="activeView === 'overview'"
      id="sycm-panel-overview"
      class="page-block sycm-section"
      role="tabpanel"
      aria-labelledby="sycm-tab-overview"
    >
      <header class="sycm-section__head">
        <h3>店铺经营表现</h3>
        <span>{{ selectedShop ? '当前店铺' : '按支付金额排序' }}</span>
      </header>
      <!-- 这个 div 就是被 ResizeObserver 量的那块：flex 把面板剩下的高度全给它，
           每页行数按它的实测高度算。表格拿到显式 :height 是为了兜底 —— 万一行高
           估偏了，代价是表格内部出一小截滚动条，而不是整页被顶出视口。 -->
      <div ref="tableAreaRef" class="sycm-table-area">
        <el-table
          v-if="paginatedOverviewRows.length"
          :data="paginatedOverviewRows"
          stripe
          :height="tableAreaHeight || undefined"
          class="sycm-table"
        >
          <el-table-column label="店铺" min-width="200">
            <template #default="{ row }">
              <div class="sycm-shop-cell">
                <span class="sycm-rank" :class="{ 'is-top': row.rank <= 3 }">{{ row.rank }}</span>
                <span class="sycm-shop-text">
                  <strong>{{ row.shopName }}</strong>
                  <small>{{ row.shopId }}</small>
                  <el-tag v-if="row.sessionFailed" type="danger" size="small">会话失效</el-tag>
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="amount" label="支付金额" min-width="120" align="right">
            <template #default="{ row }"><span class="sycm-amount">{{ row.amount }}</span></template>
          </el-table-column>
          <el-table-column prop="uv" label="访客数" min-width="100" align="right" />
          <el-table-column prop="buyers" label="支付买家" min-width="100" align="right" />
          <el-table-column prop="rate" label="转化率" min-width="100" align="right" />
          <el-table-column prop="avgPrice" label="客单价" min-width="100" align="right" />
        </el-table>
        <el-empty v-else description="当前周期暂无正式数据" />
      </div>
      <div v-if="overviewRows.length > overviewPageSize" class="sycm-pagination">
        <el-pagination
          v-model:current-page="overviewPage"
          :page-size="overviewPageSize"
          :total="overviewRows.length"
          layout="total, prev, pager, next"
          size="small"
        />
      </div>
    </section>

    <section
      v-else-if="activeView === 'sources'"
      id="sycm-panel-sources"
      class="page-block sycm-section"
      role="tabpanel"
      aria-labelledby="sycm-tab-sources"
    >
      <header class="sycm-section__head">
        <h3>流量来源构成</h3>
        <span>{{ period === 'today' ? '实时来源数据' : '历史周期暂未采集来源明细' }}</span>
      </header>
      <div ref="tableAreaRef" class="sycm-table-area">
        <el-table
          v-if="paginatedSourceRows.length"
          :data="paginatedSourceRows"
          stripe
          :height="tableAreaHeight || undefined"
          class="sycm-table"
        >
          <el-table-column prop="name" label="来源渠道" min-width="200" />
          <el-table-column prop="uv" label="访客数" min-width="110" align="right" />
          <el-table-column prop="buyers" label="支付买家" min-width="110" align="right" />
          <el-table-column prop="amount" label="支付金额" min-width="130" align="right" />
          <el-table-column prop="rate" label="转化率" min-width="110" align="right" />
        </el-table>
        <el-empty
          v-else
          :description="period === 'today' ? '暂无流量来源数据' : '该周期暂无流量来源明细'"
        />
      </div>
      <div v-if="sourceRows.length > sourcePageSize" class="sycm-pagination">
        <el-pagination
          v-model:current-page="sourcePage"
          :page-size="sourcePageSize"
          :total="sourceRows.length"
          layout="total, prev, pager, next"
          size="small"
        />
      </div>
    </section>

    <section
      v-else-if="activeView === 'details'"
      id="sycm-panel-details"
      class="page-block sycm-section"
      role="tabpanel"
      aria-labelledby="sycm-tab-details"
    >
      <header class="sycm-section__head">
        <h3>详细经营指标</h3>
        <span>仅展示已采集指标</span>
      </header>
      <!-- 这两个页签没有分页器兜底（卡片数量由采集到的指标决定），所以溢出时
           在面板内部滚，而不是把整页顶高 -->
      <div v-if="detailCards.length" class="sycm-scroll-area">
        <div class="sycm-detail-grid">
          <article v-for="item in detailCards" :key="item.field" class="sycm-detail">
            <span class="sycm-detail__name">{{ item.label }}</span>
            <strong class="sycm-detail__value">{{ item.value }}</strong>
            <span class="sycm-detail__tag">已采集</span>
          </article>
        </div>
      </div>
      <el-empty v-else description="当前数据没有更多指标" />
    </section>

    <!-- 这两块是卡片，没有分页器可以约束高度，所以让它们在自己的容器里滚，
         而不是把整页顶长。 -->
    <div
      v-else
      id="sycm-panel-status"
      class="sycm-panel-stack sycm-scroll-area"
      role="tabpanel"
      aria-labelledby="sycm-tab-status"
    >
      <section class="page-block sycm-section">
        <header class="sycm-section__head">
          <h3>采集设备</h3>
          <span>{{ collectableDeviceCount }} / {{ onlineDeviceCount }} 台可采集</span>
        </header>
        <div v-if="devices.length" class="sycm-status-grid">
          <article v-for="device in devices" :key="device.deviceId" class="sycm-status">
            <span class="sycm-status__icon">
              <el-icon><Cellphone /></el-icon>
            </span>
            <span class="sycm-status__text">
              <strong>{{ device.deviceName || device.deviceId }}</strong>
              <small>{{ device.shopCount || 0 }} 家店铺 · {{ formatDateTime(device.lastSeenAt) }}</small>
              <!-- The blocker, spelled out. "在线" alone used to imply the device
                   was collecting, which is wrong whenever Qianniu holds the
                   cookie DBs. -->
              <small v-if="device.online && device.sessionState !== 'ready'" class="sycm-status__hint">
                {{ deviceSessionHint(device) }}
              </small>
            </span>
            <span class="sycm-status__tags">
              <el-tag :type="device.online ? 'success' : 'danger'" size="small" round>
                {{ device.online ? '已连接' : '未连接' }}
              </el-tag>
              <el-tag v-if="device.online" :type="sessionTagType(device.sessionState)" size="small" round>
                {{ sessionLabel(device.sessionState) }}
              </el-tag>
            </span>
          </article>
        </div>
        <el-empty v-else description="暂无采集设备" />
      </section>

      <section class="page-block sycm-section">
        <header class="sycm-section__head">
          <h3>最近同步状态</h3>
          <span>{{ syncTask ? `任务 #${syncTask.id}` : '暂无任务' }}</span>
        </header>
        <div v-if="syncTask?.results?.length" class="sycm-status-grid">
          <article
            v-for="(result, index) in syncTask.results"
            :key="`${result.shopId ?? 'shop'}-${index}`"
            class="sycm-status"
          >
            <span class="sycm-status__icon">
              <el-icon><Sell /></el-icon>
            </span>
            <span class="sycm-status__text">
              <strong>{{ result.shopName || result.shopId }}</strong>
              <small v-if="result.error">{{ result.error }}</small>
            </span>
            <el-tag :type="result.success ? 'success' : 'danger'" size="small" round>
              {{ result.success ? '成功' : '失败' }}
            </el-tag>
          </article>
        </div>
        <el-empty v-else description="同步后将在这里显示每个店铺的结果" />
      </section>
    </div>
  </div>
</template>

<style scoped>
.tone-indigo {
  --tone: #6366f1;
  --tone-soft: rgba(99, 102, 241, 0.11);
}

.tone-sky {
  --tone: #0284c7;
  --tone-soft: rgba(14, 165, 233, 0.1);
}

.tone-teal {
  --tone: #059669;
  --tone-soft: rgba(16, 185, 129, 0.11);
}

.tone-violet {
  --tone: #7c3aed;
  --tone-soft: rgba(139, 92, 246, 0.1);
}

.tone-amber {
  --tone: #b45309;
  --tone-soft: rgba(245, 158, 11, 0.12);
}

/* 整页一屏，永不滚动 —— 和 style.css 里 .list-surface--fixed 同一套路（那边也是
   calc(100vh - 104px)：AdminLayout 顶栏 min-height 60px + 内容区上下 padding 44px）。
   之前这里是 .page-stack，六个 page-block 竖着摞，总高必然超视口，才会出现整页滚动条。
   现在 chrome（标题/筛选/KPI/页签）按自然高度占位，剩下的高度全给当前页签。 */
.sycm-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: calc(100vh - 104px);
  min-width: 0;
  overflow: hidden;
}

/* chrome：不伸不缩，按内容高度 */
.sycm-page > .sycm-top,
.sycm-page > .sycm-controlbar,
.sycm-page > .sycm-kpis,
.sycm-page > .sycm-nav,
.sycm-page > .el-alert {
  flex: 0 0 auto;
}

/* 当前页签：吃掉剩余高度。min-height: 0 是关键，否则 flex 子项不肯缩到内容以下，
   内部的 overflow 就永远不生效。 */
.sycm-page > [role='tabpanel'] {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
}

/* 被 ResizeObserver 量的那块 */
.sycm-table-area {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

/* 没有分页器约束高度的页签（详细指标 / 同步状态）在自己容器内滚 */
.sycm-scroll-area {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.sycm-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}

.sycm-title h2 {
  margin: 0;
  color: var(--text-main);
  font-size: 20px;
  font-weight: 700;
}

.sycm-title p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 12.5px;
}

.sycm-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* align-items: start keeps the two field labels on one baseline; the controls
   below them are matched to 32px so their bottoms line up too. */
.sycm-controlbar {
  display: grid;
  grid-template-columns: minmax(220px, 300px) auto 1fr;
  gap: 18px;
  align-items: start;
  padding: 14px 16px;
}

.sycm-field {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.sycm-field__label {
  color: var(--text-secondary);
  font-size: 11.5px;
  font-weight: 600;
}

.sycm-segments {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 3px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: #f6f7f9;
}

.sycm-segment {
  min-width: 56px;
  height: 24px;
  padding: 0 10px;
  border: 0;
  border-radius: 6px;
  color: var(--text-secondary);
  background: transparent;
  font-size: 12px;
  cursor: pointer;
  transition: color 0.16s ease, background-color 0.16s ease, box-shadow 0.16s ease;
}

.sycm-segment:hover:not(:disabled) {
  color: var(--brand-primary);
}

.sycm-segment.is-active {
  color: var(--brand-primary);
  background: #ffffff;
  font-weight: 700;
  box-shadow: 0 1px 4px rgba(17, 24, 39, 0.12);
}

.sycm-segment:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.sycm-freshness {
  align-self: end;
  justify-self: end;
  color: var(--text-secondary);
  font-size: 11.5px;
  text-align: right;
}

.sycm-freshness strong {
  color: var(--text-main);
  font-weight: 600;
}

/* Fixed columns, not auto-fit: the 1px gap doubles as the cell divider, so a
   partly-filled last row would leave the container's grey showing through.
   6 cards divide evenly by 6 / 3 / 2, so every row is always full at every
   breakpoint. Kept on one row on wide screens specifically to keep the page
   short -- a second KPI row costs ~105px and pushes the table out of view. */
.sycm-kpis {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 1px;
  overflow: hidden;
  background: var(--panel-border);
  border-radius: var(--panel-radius);
}

.sycm-kpi {
  position: relative;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  grid-template-areas:
    'icon label'
    'icon value'
    'note note';
  gap: 2px 10px;
  min-width: 0;
  padding: 15px 16px;
  background: var(--panel-bg);
}

.sycm-kpi__icon {
  grid-area: icon;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: var(--tone-soft);
  color: var(--tone);
  font-size: 17px;
}

.sycm-kpi__label {
  grid-area: label;
  align-self: end;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 11.5px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.sycm-kpi__value {
  grid-area: value;
  align-self: start;
  overflow: hidden;
  color: var(--tone);
  font-size: 20px;
  font-weight: 700;
  line-height: 1.25;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.sycm-kpi__note {
  grid-area: note;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #eef0f3;
  color: #98a1ae;
  font-size: 10.5px;
  line-height: 1.45;
}

/* Sits in a panel so the tabs align with the section content above and below
   instead of floating flush against the page background. The active underline
   overlays the panel's own bottom border. */
.sycm-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 42px;
  padding: 0 16px;
}

.sycm-tabs {
  display: flex;
  align-items: center;
  gap: 24px;
}

.sycm-tab {
  position: relative;
  height: 42px;
  padding: 0 1px;
  border: 0;
  color: var(--text-secondary);
  background: transparent;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
}

.sycm-tab:hover {
  color: var(--text-main);
}

.sycm-tab.is-active {
  color: var(--brand-primary);
  font-weight: 700;
}

.sycm-tab.is-active::after {
  content: '';
  position: absolute;
  right: 0;
  bottom: -1px;
  left: 0;
  height: 2px;
  border-radius: 999px;
  background: var(--brand-primary);
}

.sycm-context {
  color: var(--text-secondary);
  font-size: 11.5px;
}

.sycm-section {
  overflow: hidden;
}

/* flex, not grid: 这个元素同时匹配 .sycm-page > [role='tabpanel']（0,2,0），
   那条规则的 display: flex 会盖掉这里写 grid，写 grid 只会误导人。
   子面板 flex: 0 0 auto —— 容器是滚动的，不能让两块被压扁去凑高度。 */
.sycm-panel-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.sycm-panel-stack > .sycm-section {
  flex: 0 0 auto;
}

/* flex: 0 0 auto —— 面板是 flex 列，表头和分页条必须守住自己的高度，
   把剩下的全让给中间的表格区（.sycm-table-area），否则它们会被压扁 */
.sycm-section__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 0 0 auto;
  gap: 12px;
  padding: 13px 16px;
  border-bottom: 1px solid var(--panel-border);
  background: #fcfcfd;
}

.sycm-section__head h3 {
  position: relative;
  margin: 0;
  padding-left: 10px;
  color: var(--text-main);
  font-size: 14px;
  font-weight: 700;
}

.sycm-section__head h3::before {
  content: '';
  position: absolute;
  top: 2px;
  bottom: 2px;
  left: 0;
  width: 3px;
  border-radius: 999px;
  background: var(--brand-primary);
}

.sycm-section__head span {
  color: var(--text-secondary);
  font-size: 11.5px;
}

.sycm-table {
  width: 100%;
}

.sycm-pagination {
  display: flex;
  justify-content: flex-end;
  flex: 0 0 auto;
  padding: 10px 16px;
  border-top: 1px solid var(--panel-border);
}

.sycm-table :deep(.el-table__cell) {
  font-variant-numeric: tabular-nums;
}

.sycm-shop-cell {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}

.sycm-rank {
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  width: 21px;
  height: 21px;
  border-radius: 6px;
  background: #f3f4f6;
  color: var(--text-secondary);
  font-size: 10.5px;
  font-weight: 700;
}

.sycm-rank.is-top {
  background: rgba(99, 102, 241, 0.11);
  color: var(--brand-primary);
}

.sycm-shop-text {
  display: grid;
  min-width: 0;
  line-height: 1.4;
}

.sycm-shop-text strong {
  overflow: hidden;
  font-weight: 650;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.sycm-shop-text small {
  color: #98a1ae;
  font-size: 10.5px;
}

.sycm-amount {
  color: #059669;
  font-weight: 700;
}

/* Card grid rather than border-divided cells: detailCards is filtered by what
   was actually collected, so the count is arbitrary. Per-cell right/bottom
   borders left a stub hanging in the empty part of the last row and doubled up
   against the panel's own bottom border. Matches .sycm-status-grid. */
.sycm-detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(165px, 1fr));
  gap: 10px;
  padding: 14px;
}

.sycm-detail {
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
}

.sycm-detail__name {
  color: var(--text-secondary);
  font-size: 11.5px;
}

.sycm-detail__value {
  display: block;
  margin-top: 6px;
  color: var(--text-main);
  font-size: 18px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.sycm-detail__tag {
  display: inline-flex;
  margin-top: 7px;
  padding: 2px 6px;
  border-radius: 5px;
  background: rgba(16, 185, 129, 0.09);
  color: #059669;
  font-size: 10px;
}

.sycm-status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding: 14px;
}

.sycm-status {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 12px 13px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
}

.sycm-status__icon {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.1);
  color: var(--brand-primary);
  font-size: 15px;
}

.sycm-status__text {
  display: grid;
  flex: 1 1 auto;
  min-width: 0;
  line-height: 1.4;
}

.sycm-status__text strong {
  overflow: hidden;
  font-size: 12.5px;
  font-weight: 650;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.sycm-status__text small {
  overflow: hidden;
  color: #98a1ae;
  font-size: 10.5px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* The blocker line wraps: it carries the agent's own breakdown (locked 9 /
   logged_out 8 / ...), which does not fit on one ellipsised line. */
.sycm-status__hint {
  margin-top: 2px;
  color: #b45309 !important;
  white-space: normal !important;
}

.sycm-status__tags {
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: flex-end;
}

/* 6 -> 3 -> 2, never a partial row (see .sycm-kpis) */
@media (max-width: 1400px) {
  .sycm-kpis {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1150px) {
  .sycm-status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .sycm-controlbar {
    grid-template-columns: 1fr;
    gap: 12px;
    padding: 12px;
  }

  .sycm-segments {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    width: 100%;
  }

  .sycm-segment {
    min-width: 0;
    padding: 0 4px;
  }

  .sycm-freshness {
    justify-self: start;
    text-align: left;
  }
}

@media (max-width: 768px) {
  /* 手机上放开视口锁定：竖屏没有那么多高度可分，钉死 100vh 会把表格压到只剩
     两三行。这里让整页恢复正常文档流滚动，表格也交回自然高度。 */
  .sycm-page {
    height: auto;
    overflow: visible;
  }

  .sycm-table-area,
  .sycm-scroll-area {
    overflow: visible;
  }

  .sycm-title p {
    display: none;
  }

  .sycm-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .sycm-kpi {
    padding: 13px;
  }

  .sycm-kpi__value {
    font-size: 18px;
  }

  .sycm-tabs {
    width: 100%;
    justify-content: space-between;
    gap: 0;
  }

  .sycm-tab {
    font-size: 11.5px;
  }

  .sycm-context {
    display: none;
  }

  .sycm-detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    padding: 12px;
  }

  .sycm-status-grid {
    grid-template-columns: 1fr;
  }
}
</style>
