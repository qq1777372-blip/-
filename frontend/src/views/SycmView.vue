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
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  createSycmSyncRequest,
  fetchSycmCollectorDevices,
  fetchSycmLatest,
  fetchSycmLatestSyncRequest,
} from '../api'
import type {
  SycmCollectorDevice,
  SycmPeriod,
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

const kpiCards = computed(() => {
  const list = visibleShops.value
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
        amount: formatMoney(amount),
        uv: formatNumber(uv),
        buyers: formatNumber(buyers),
        rate: formatPercent(uv && buyers !== null ? buyers / uv : null),
        avgPrice: formatMoney(buyers && amount !== null ? amount / buyers : null),
      }
    }),
)

const sourceRows = computed(() => {
  // 只有今日快照带来源明细，历史周期后端不返回 sourceTree
  if (period.value !== 'today') return []
  const merged = new Map<string, { name: string; uv: number; buyers: number; amount: number }>()

  visibleShops.value.forEach((shop) => {
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
    .map((item) => ({ ...item, raw: sumMetric(visibleShops.value, item.field) }))
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
    const task = await createSycmSyncRequest()
    syncTask.value = task

    for (let attempt = 0; attempt < 90; attempt += 1) {
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
      ElMessage.warning('同步超时，请稍后在同步状态中查看结果')
    }
  } catch (error) {
    if (!syncCancelled) {
      ElMessage.error(error instanceof Error ? error.message : '同步失败')
    }
  } finally {
    syncing.value = false
  }
}

onMounted(load)

onBeforeUnmount(() => {
  // 离开页面时终止轮询，避免定时器在组件销毁后继续回写状态
  syncCancelled = true
  if (syncTimer !== null) {
    clearTimeout(syncTimer)
    syncTimer = null
  }
})
</script>

<template>
  <div class="page-stack sycm-page">
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
        <span class="sycm-field__label">数据周期</span>
        <div class="sycm-segments">
          <button
            v-for="item in periods"
            :key="item.value"
            type="button"
            class="sycm-segment"
            :class="{ 'is-active': period === item.value }"
            :disabled="loading"
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

    <nav class="sycm-nav">
      <div class="sycm-tabs">
        <button
          v-for="item in views"
          :key="item.value"
          type="button"
          class="sycm-tab"
          :class="{ 'is-active': activeView === item.value }"
          @click="activeView = item.value"
        >
          {{ item.label }}
        </button>
      </div>
      <span class="sycm-context">{{ contextLabel }}</span>
    </nav>

    <section v-if="activeView === 'overview'" class="page-block sycm-section">
      <header class="sycm-section__head">
        <h3>店铺经营表现</h3>
        <span>{{ selectedShop ? '当前店铺' : '按支付金额排序' }}</span>
      </header>
      <!-- max-height, not an unbounded table: with 13 shops the two-line cells
           grew the page past the viewport, so the whole layout scrolled instead
           of just the rows. Element Plus keeps the header pinned and scrolls the
           body, matching DashboardView's server-status table. -->
      <el-table
        v-if="overviewRows.length"
        :data="overviewRows"
        stripe
        max-height="520"
        class="sycm-table"
      >
        <el-table-column label="店铺" min-width="220">
          <template #default="{ row }">
            <div class="sycm-shop-cell">
              <span class="sycm-rank" :class="{ 'is-top': row.rank <= 3 }">{{ row.rank }}</span>
              <span class="sycm-shop-text">
                <strong>{{ row.shopName }}</strong>
                <small>{{ row.shopId }}</small>
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="支付金额" min-width="130" align="right">
          <template #default="{ row }"><span class="sycm-amount">{{ row.amount }}</span></template>
        </el-table-column>
        <el-table-column prop="uv" label="访客数" min-width="110" align="right" />
        <el-table-column prop="buyers" label="支付买家" min-width="110" align="right" />
        <el-table-column prop="rate" label="转化率" min-width="110" align="right" />
        <el-table-column prop="avgPrice" label="客单价" min-width="120" align="right" />
      </el-table>
      <el-empty v-else description="当前周期暂无正式数据" />
    </section>

    <section v-else-if="activeView === 'sources'" class="page-block sycm-section">
      <header class="sycm-section__head">
        <h3>流量来源构成</h3>
        <span>{{ period === 'today' ? '实时来源数据' : '历史周期暂未采集来源明细' }}</span>
      </header>
      <el-table
        v-if="sourceRows.length"
        :data="sourceRows"
        stripe
        max-height="520"
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
    </section>

    <section v-else-if="activeView === 'details'" class="page-block sycm-section">
      <header class="sycm-section__head">
        <h3>详细经营指标</h3>
        <span>仅展示已采集指标</span>
      </header>
      <div v-if="detailCards.length" class="sycm-detail-grid">
        <article v-for="item in detailCards" :key="item.field" class="sycm-detail">
          <span class="sycm-detail__name">{{ item.label }}</span>
          <strong class="sycm-detail__value">{{ item.value }}</strong>
          <span class="sycm-detail__tag">已采集</span>
        </article>
      </div>
      <el-empty v-else description="当前数据没有更多指标" />
    </section>

    <template v-else>
      <section class="page-block sycm-section">
        <header class="sycm-section__head">
          <h3>采集设备</h3>
          <span>{{ onlineDeviceCount }} 台在线</span>
        </header>
        <div v-if="devices.length" class="sycm-status-grid">
          <article v-for="device in devices" :key="device.deviceId" class="sycm-status">
            <span class="sycm-status__icon">
              <el-icon><Cellphone /></el-icon>
            </span>
            <span class="sycm-status__text">
              <strong>{{ device.deviceName || device.deviceId }}</strong>
              <small>{{ device.shopCount || 0 }} 家店铺 · {{ formatDateTime(device.lastSeenAt) }}</small>
            </span>
            <el-tag :type="device.online ? 'success' : 'danger'" size="small" round>
              {{ device.online ? '在线' : '离线' }}
            </el-tag>
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
    </template>
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

.sycm-controlbar {
  display: grid;
  grid-template-columns: minmax(220px, 300px) auto 1fr;
  gap: 18px;
  align-items: end;
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
  padding: 3px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: #f6f7f9;
}

.sycm-segment {
  min-width: 56px;
  height: 28px;
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
  justify-self: end;
  color: var(--text-secondary);
  font-size: 11.5px;
  text-align: right;
}

.sycm-freshness strong {
  color: var(--text-main);
  font-weight: 600;
}

.sycm-kpis {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  overflow: hidden;
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
}

.sycm-kpi + .sycm-kpi {
  border-left: 1px solid var(--panel-border);
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

.sycm-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 42px;
  border-bottom: 1px solid var(--panel-border);
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

.sycm-section__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
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

.sycm-detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.sycm-detail {
  min-width: 0;
  padding: 15px 16px;
  border-right: 1px solid var(--panel-border);
  border-bottom: 1px solid var(--panel-border);
}

.sycm-detail:nth-child(4n) {
  border-right: 0;
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

@media (max-width: 1150px) {
  .sycm-kpis {
    grid-template-columns: repeat(3, 1fr);
  }

  .sycm-kpi:nth-child(4) {
    border-left: 0;
  }

  .sycm-kpi:nth-child(n + 4) {
    border-top: 1px solid var(--panel-border);
  }

  .sycm-detail-grid {
    grid-template-columns: repeat(3, 1fr);
  }

  .sycm-detail:nth-child(4n) {
    border-right: 1px solid var(--panel-border);
  }

  .sycm-detail:nth-child(3n) {
    border-right: 0;
  }

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
  .sycm-title p {
    display: none;
  }

  .sycm-kpis {
    grid-template-columns: repeat(2, 1fr);
  }

  .sycm-kpi {
    padding: 13px;
  }

  .sycm-kpi:nth-child(4) {
    border-left: 1px solid var(--panel-border);
  }

  .sycm-kpi:nth-child(odd) {
    border-left: 0;
  }

  .sycm-kpi:nth-child(n + 3) {
    border-top: 1px solid var(--panel-border);
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
    grid-template-columns: repeat(2, 1fr);
  }

  .sycm-detail:nth-child(3n) {
    border-right: 1px solid var(--panel-border);
  }

  .sycm-detail:nth-child(even) {
    border-right: 0;
  }

  .sycm-status-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 480px) {
  .sycm-kpis {
    grid-template-columns: 1fr;
  }

  .sycm-kpi:nth-child(n) {
    border-left: 0;
  }

  .sycm-kpi + .sycm-kpi {
    border-top: 1px solid var(--panel-border);
  }
}
</style>
