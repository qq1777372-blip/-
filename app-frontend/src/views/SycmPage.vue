<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { IonButton, IonContent, IonIcon, IonPage, IonRefresher, IonRefresherContent, toastController } from '@ionic/vue'
import { refreshOutline, syncOutline } from 'ionicons/icons'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'

type Metric = { value: number | null; cycleCrc: unknown }
type SourceNode = { pageName?: { value?: string }; uv?: Metric; payByrCnt?: Metric; payAmt?: Metric }
type Shop = {
  id: number
  shopId: string
  shopName: string
  collectedAt: string
  receivedAt: string
  period: string
  overview: Record<string, Metric>
  sourceTree: SourceNode[]
  availableDays?: number
  uv?: number | null
  pv?: number | null
  cartByrCnt?: number | null
  payByrCnt?: number | null
  payAmt?: number | null
  payRate?: number | null
}
type Device = { deviceId: string; deviceName: string; online: boolean; shopCount: number; lastSeenAt: string }
type SyncResult = { shopId: string; shopName: string; success: boolean }
type SyncRequest = { id: number; status: 'pending' | 'running' | 'completed' | 'failed'; error: string; results?: SyncResult[] }
type Period = 'today' | 'yesterday' | 'recent7' | 'recent30'
type View = 'overview' | 'sources' | 'details' | 'status'

const periods: [Period, string][] = [['today', '今日'], ['yesterday', '昨日'], ['recent7', '近7天'], ['recent30', '近30天']]
const views: [View, string][] = [['overview', '店铺概览'], ['sources', '流量来源'], ['details', '详细指标'], ['status', '同步状态']]
const details: [string, string, 'number' | 'money' | 'percent'][] = [
  ['itmUv', '商品访客', 'number'], ['itmPv', '商品浏览', 'number'], ['newUv', '新访客', 'number'], ['oldUv', '老访客', 'number'],
  ['cltCnt', '收藏次数', 'number'], ['shopCltByrCnt', '店铺收藏人数', 'number'], ['itmCltByrCnt', '商品收藏人数', 'number'], ['crtByrCnt', '下单买家', 'number'],
  ['payOrdCnt', '支付订单', 'number'], ['uvValue', '访客价值', 'money'], ['payPct', '客单价', 'money'], ['crtRate', '下单转化率', 'percent'],
]

const period = ref<Period>('today')
const shopId = ref('')
const view = ref<View>('overview')
const shops = ref<Shop[]>([])
const devices = ref<Device[]>([])
const syncing = ref(false)
const syncTask = ref<SyncRequest | null>(null)
const loadError = ref('')

const number = (value: number | null | undefined) => value == null ? '--' : new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)
const money = (value: number | null | undefined) => value == null ? '--' : `¥${number(value)}`
const percent = (value: number | null | undefined) => value == null ? '--' : `${(Number(value) * 100).toFixed(2)}%`
const dateTime = (value: string) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '暂无'
const format = (value: number | null, type: 'number' | 'money' | 'percent') => type === 'money' ? money(value) : type === 'percent' ? percent(value) : number(value)

const valueOf = (shop: Shop, field: string): number | null => {
  const metric = shop.overview?.[field]?.value
  if (metric != null) return Number(metric)
  const flat = (shop as unknown as Record<string, unknown>)[field]
  return typeof flat === 'number' ? flat : null
}
const sum = (list: Shop[], field: string): number | null => {
  const values = list.map((shop) => valueOf(shop, field)).filter((value): value is number => value != null)
  return values.length ? values.reduce((total, value) => total + Number(value || 0), 0) : null
}

const scoped = computed(() => shopId.value ? shops.value.filter((shop) => shop.shopId === shopId.value) : shops.value)
const freshness = computed(() => scoped.value.reduce((last, shop) => !last || shop.collectedAt > last ? shop.collectedAt : last, ''))
const periodLabel = computed(() => periods.find(([value]) => value === period.value)?.[1] || '今日')
const onlineCount = computed(() => devices.value.filter((device) => device.online).length)

const kpis = computed(() => {
  const list = scoped.value
  const uv = sum(list, 'uv'), pv = sum(list, 'pv'), cart = sum(list, 'cartByrCnt')
  const buyers = sum(list, 'payByrCnt'), amount = sum(list, 'payAmt')
  const rate = uv && buyers != null ? buyers / uv : null
  return [
    { label: '访客数', value: number(uv), note: '覆盖店铺访问用户', tone: 'primary' },
    { label: '浏览量', value: number(pv), note: '页面浏览总量', tone: '' },
    { label: '加购人数', value: number(cart), note: cart == null ? '当前周期暂无该指标' : '产生加购的用户', tone: '' },
    { label: '支付买家', value: number(buyers), note: '完成支付的用户', tone: '' },
    { label: '支付金额', value: money(amount), note: '成交支付金额', tone: 'revenue' },
    { label: '支付转化率', value: percent(rate), note: '支付买家 / 访客', tone: '' },
  ]
})

const ranked = computed(() => [...scoped.value]
  .sort((a, b) => Number(valueOf(b, 'payAmt') || 0) - Number(valueOf(a, 'payAmt') || 0))
  .map((shop) => {
    const uv = valueOf(shop, 'uv'), buyers = valueOf(shop, 'payByrCnt'), amount = valueOf(shop, 'payAmt')
    return {
      shopId: shop.shopId,
      shopName: shop.shopName || shop.shopId,
      amount: money(amount),
      uv: number(uv),
      buyers: number(buyers),
      rate: percent(uv && buyers != null ? buyers / uv : null),
      unitPrice: money(buyers && amount != null ? amount / buyers : null),
    }
  }))

const sources = computed(() => {
  if (period.value !== 'today') return []
  const grouped = new Map<string, { name: string; uv: number; buyers: number; amount: number }>()
  scoped.value.forEach((shop) => (Array.isArray(shop.sourceTree) ? shop.sourceTree : []).forEach((source) => {
    const name = source?.pageName?.value || '其他来源'
    const current = grouped.get(name) || { name, uv: 0, buyers: 0, amount: 0 }
    current.uv += Number(source?.uv?.value || 0)
    current.buyers += Number(source?.payByrCnt?.value || 0)
    current.amount += Number(source?.payAmt?.value || 0)
    grouped.set(name, current)
  }))
  return [...grouped.values()].sort((a, b) => b.uv - a.uv)
})

const detailMetrics = computed(() => details
  .map(([field, label, type]) => ({ field, label, value: sum(scoped.value, field), type }))
  .filter((item) => item.value != null))

async function load(event?: { target: { complete: () => void } }) {
  try {
    shops.value = await api<Shop[]>(`/api/sycm/latest?period=${period.value}`)
    if (shopId.value && !shops.value.some((shop) => shop.shopId === shopId.value)) shopId.value = ''
    syncTask.value = await api<SyncRequest | null>('/api/sycm/sync-requests/latest').catch(() => syncTask.value)
    devices.value = await api<Device[]>('/api/sycm/collector-devices').catch(() => devices.value)
    loadError.value = ''
  } catch (error) {
    loadError.value = error instanceof ApiError ? error.detail : error instanceof Error ? error.message : '数据加载失败'
  } finally {
    event?.target.complete()
  }
}

async function selectPeriod(value: Period) {
  period.value = value
  await load()
}

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

async function syncData() {
  if (syncing.value) return
  syncing.value = true
  try {
    const task = await api<SyncRequest>('/api/sycm/sync-requests', { method: 'POST' })
    syncTask.value = task
    for (let attempt = 0; attempt < 90; attempt += 1) {
      const current = await api<SyncRequest | null>('/api/sycm/sync-requests/latest')
      syncTask.value = current
      if (current?.id === task.id && current.status === 'completed') {
        await load()
        view.value = 'status'
        return
      }
      if (current?.id === task.id && current.status === 'failed') throw new Error(current.error || '采集端同步失败')
      await wait(2000)
    }
  } catch (error) {
    const message = error instanceof ApiError ? error.detail : error instanceof Error ? error.message : '同步失败'
    const toast = await toastController.create({ message, duration: 2200, color: 'danger' })
    await toast.present()
  } finally {
    syncing.value = false
  }
}

onMounted(() => load())
</script>

<template>
  <IonPage>
    <PageHeader title="生意参谋" subtitle="多店铺经营数据工作台" back />
    <IonContent>
      <IonRefresher slot="fixed" @ion-refresh="load"><IonRefresherContent /></IonRefresher>
      <main class="page-pad sycm-page">
        <div v-if="loadError" class="sc-empty sc-section">{{ loadError }}</div>
        <template v-else>
          <header class="sc-top">
            <div class="sc-title">
              <h1>生意参谋</h1>
              <p>多店铺经营数据工作台</p>
            </div>
            <div class="sc-actions">
              <IonButton size="small" fill="outline" @click="load()"><IonIcon slot="start" :icon="refreshOutline" />刷新</IonButton>
              <IonButton size="small" :disabled="syncing" @click="syncData"><IonIcon slot="start" :icon="syncOutline" />{{ syncing ? '同步中...' : '同步数据' }}</IonButton>
            </div>
          </header>

          <section class="sc-controlbar">
            <label class="sc-field">
              <span class="sc-label">店铺范围</span>
              <select v-model="shopId" class="sc-select">
                <option value="">全部店铺（{{ shops.length }}）</option>
                <option v-for="shop in shops" :key="shop.shopId" :value="shop.shopId">{{ shop.shopName || shop.shopId }}</option>
              </select>
            </label>
            <div class="sc-field">
              <span class="sc-label">数据周期</span>
              <div class="sc-periods">
                <button v-for="[value, label] in periods" :key="value" type="button" :class="['sc-segment', { active: period === value }]" @click="selectPeriod(value)">{{ label }}</button>
              </div>
            </div>
            <div class="sc-freshness">数据更新：{{ dateTime(freshness) }}</div>
          </section>

          <section class="sc-kpis">
            <div v-for="kpi in kpis" :key="kpi.label" :class="['sc-kpi', kpi.tone]">
              <span class="sc-kpi-label">{{ kpi.label }}</span>
              <strong class="sc-kpi-value">{{ kpi.value }}</strong>
              <span class="sc-kpi-note">{{ kpi.note }}</span>
            </div>
          </section>

          <nav class="sc-nav">
            <div class="sc-tabs">
              <button v-for="[value, label] in views" :key="value" type="button" :class="['sc-tab', { active: view === value }]" @click="view = value">{{ label }}</button>
            </div>
            <span class="sc-context">{{ periodLabel }} · {{ shopId ? '单店' : `${shops.length} 家店铺` }}</span>
          </nav>

          <section v-if="view === 'overview'" class="sc-section">
            <header class="sc-section-head">
              <h2>店铺经营表现</h2>
              <span>{{ shopId ? '当前店铺' : '按支付金额排序' }}</span>
            </header>
            <div v-if="!ranked.length" class="sc-empty">当前周期暂无正式数据</div>
            <div v-else class="sc-table-wrap">
              <table class="sc-table">
                <thead><tr><th>店铺</th><th>支付金额</th><th>访客数</th><th>支付买家</th><th>转化率</th><th>客单价</th></tr></thead>
                <tbody>
                  <tr v-for="(row, index) in ranked" :key="row.shopId" @click="shopId = row.shopId">
                    <td>
                      <span class="sc-rank">{{ index + 1 }}</span>
                      <span class="sc-shop-name">{{ row.shopName }}</span>
                      <span class="sc-shop-id">{{ row.shopId }}</span>
                    </td>
                    <td class="sc-positive">{{ row.amount }}</td>
                    <td>{{ row.uv }}</td>
                    <td>{{ row.buyers }}</td>
                    <td>{{ row.rate }}</td>
                    <td>{{ row.unitPrice }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section v-else-if="view === 'sources'" class="sc-section">
            <header class="sc-section-head">
              <h2>流量来源构成</h2>
              <span>{{ period === 'today' ? '实时来源数据' : '历史周期暂未采集来源明细' }}</span>
            </header>
            <div v-if="!sources.length" class="sc-empty">{{ period === 'today' ? '暂无流量来源数据' : '该周期暂无流量来源明细' }}</div>
            <div v-else class="sc-table-wrap">
              <table class="sc-table">
                <thead><tr><th>来源渠道</th><th>访客数</th><th>支付买家</th><th>支付金额</th><th>转化率</th></tr></thead>
                <tbody>
                  <tr v-for="source in sources" :key="source.name">
                    <td>{{ source.name }}</td>
                    <td>{{ number(source.uv) }}</td>
                    <td>{{ number(source.buyers) }}</td>
                    <td>{{ money(source.amount) }}</td>
                    <td>{{ percent(source.uv ? source.buyers / source.uv : null) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section v-else-if="view === 'details'" class="sc-section">
            <header class="sc-section-head">
              <h2>详细经营指标</h2>
              <span>仅展示已采集指标</span>
            </header>
            <div v-if="!detailMetrics.length" class="sc-empty">当前数据没有更多指标</div>
            <div v-else class="sc-detail-grid">
              <div v-for="item in detailMetrics" :key="item.field" class="sc-detail">
                <span class="sc-detail-name">{{ item.label }}</span>
                <strong class="sc-detail-value">{{ format(item.value, item.type) }}</strong>
                <span class="sc-detail-trend">已采集</span>
              </div>
            </div>
          </section>

          <template v-else>
            <section class="sc-section">
              <header class="sc-section-head">
                <h2>采集设备</h2>
                <span>{{ onlineCount }} 台在线</span>
              </header>
              <div v-if="!devices.length" class="sc-empty">暂无采集设备</div>
              <div v-else class="sc-status-list">
                <div v-for="device in devices" :key="device.deviceId" class="sc-status">
                  <span>
                    <strong>{{ device.deviceName || device.deviceId }}</strong>
                    <small class="sc-shop-id">{{ device.shopCount || 0 }} 家店铺 · {{ dateTime(device.lastSeenAt) }}</small>
                  </span>
                  <strong :class="device.online ? 'ok' : 'fail'">{{ device.online ? '在线' : '离线' }}</strong>
                </div>
              </div>
            </section>
            <section class="sc-section">
              <header class="sc-section-head">
                <h2>最近同步状态</h2>
                <span>{{ syncTask ? `任务 #${syncTask.id ?? '--'}` : '暂无任务' }}</span>
              </header>
              <div v-if="!syncTask?.results?.length" class="sc-empty">同步后将在这里显示每个店铺的结果</div>
              <div v-else class="sc-status-list">
                <div v-for="result in syncTask.results" :key="result.shopId" class="sc-status">
                  <span>{{ result.shopName || result.shopId }}</span>
                  <strong :class="result.success ? 'ok' : 'fail'">{{ result.success ? '成功' : '失败' }}</strong>
                </div>
              </div>
            </section>
          </template>
        </template>
      </main>
    </IonContent>
  </IonPage>
</template>

<style scoped>
.sycm-page{--sc-blue:#2563eb;--sc-green:#059669;--sc-red:#dc2626;--sc-ink:var(--app-text,#172033);--sc-muted:var(--app-muted,#667085);--sc-line:var(--app-line,#dfe3ea);--sc-card:var(--app-card,#fff);display:grid;gap:16px;max-width:1500px;margin:0 auto;color:var(--sc-ink)}
.sycm-page *{box-sizing:border-box}
.sc-top{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}.sc-title h1{margin:0;font-size:22px;line-height:1.35}.sc-title p{margin:5px 0 0;color:var(--sc-muted);font-size:12px}.sc-actions{display:flex;gap:8px}.sc-actions ion-button{margin:0}
.sc-controlbar{display:grid;grid-template-columns:minmax(220px,320px) auto 1fr;gap:14px;align-items:end;padding:14px 16px;border:1px solid var(--sc-line);border-radius:8px;background:var(--sc-card)}.sc-field{display:grid;gap:6px}.sc-label{color:var(--sc-muted);font-size:11px;font-weight:600}.sc-select{width:100%;height:38px;padding:0 10px;border:1px solid var(--sc-line);border-radius:6px;color:var(--sc-ink);background:var(--sc-card)}.sc-periods{display:flex;gap:4px}.sc-segment{height:38px;padding:0 16px;border:0;border-radius:5px;color:var(--sc-muted);background:transparent;cursor:pointer}.sc-segment.active{color:#fff;background:var(--sc-blue);font-weight:700}.sc-freshness{align-self:center;justify-self:end;color:var(--sc-muted);font-size:11px;text-align:right}
.sc-kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid var(--sc-line);border-radius:8px;overflow:hidden;background:var(--sc-card)}.sc-kpi{min-width:0;padding:17px 18px;border-right:1px solid var(--sc-line)}.sc-kpi:last-child{border-right:0}.sc-kpi-label{display:block;color:var(--sc-muted);font-size:12px}.sc-kpi-value{display:block;margin-top:7px;overflow:hidden;font-size:23px;line-height:1.25;text-overflow:ellipsis}.sc-kpi-note{display:block;height:17px;margin-top:5px;color:var(--sc-muted);font-size:10px}.sc-kpi.primary .sc-kpi-value{color:var(--sc-blue)}.sc-kpi.revenue .sc-kpi-value{color:var(--sc-green)}
.sc-nav{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--sc-line)}.sc-tabs{display:flex;gap:22px}.sc-tab{position:relative;padding:11px 2px;border:0;color:var(--sc-muted);background:transparent;font-weight:600;cursor:pointer}.sc-tab.active{color:var(--sc-blue)}.sc-tab.active:after{position:absolute;right:0;bottom:-1px;left:0;height:2px;background:var(--sc-blue);content:""}.sc-context{color:var(--sc-muted);font-size:11px}
.sc-section{border:1px solid var(--sc-line);border-radius:8px;background:var(--sc-card)}.sc-section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border-bottom:1px solid var(--sc-line)}.sc-section-head h2{margin:0;font-size:15px}.sc-section-head span{color:var(--sc-muted);font-size:11px}.sc-table-wrap{overflow:auto}.sc-table{width:100%;border-collapse:collapse;white-space:nowrap}.sc-table th,.sc-table td{padding:12px 16px;border-bottom:1px solid var(--sc-line);font-size:12px;text-align:right}.sc-table th{color:var(--sc-muted);font-weight:600;background:color-mix(in srgb,var(--sc-card) 92%,var(--sc-line))}.sc-table th:first-child,.sc-table td:first-child{text-align:left}.sc-table tbody tr:last-child td{border-bottom:0}.sc-table tbody tr{cursor:pointer}.sc-table tbody tr:hover{background:color-mix(in srgb,var(--sc-card) 94%,var(--sc-blue))}.sc-shop-name{font-weight:650}.sc-shop-id{display:block;margin-top:2px;color:var(--sc-muted);font-size:10px}.sc-rank{display:inline-grid;width:22px;height:22px;margin-right:9px;place-items:center;border-radius:4px;color:var(--sc-muted);background:color-mix(in srgb,var(--sc-card) 88%,var(--sc-line));font-size:10px}.sc-positive{color:var(--sc-green);font-weight:650}
.sc-detail-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))}.sc-detail{min-width:0;padding:14px 16px;border-right:1px solid var(--sc-line);border-bottom:1px solid var(--sc-line)}.sc-detail:nth-child(4n){border-right:0}.sc-detail-name{color:var(--sc-muted);font-size:11px}.sc-detail-value{display:block;margin-top:5px;font-size:18px}.sc-detail-trend{display:block;margin-top:4px;color:var(--sc-muted);font-size:10px}.sc-empty{padding:46px 16px;text-align:center;color:var(--sc-muted);font-size:13px}.sc-status-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:12px}.sc-status{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:11px 12px;border:1px solid var(--sc-line);border-radius:6px;font-size:12px}.sc-status strong.ok{color:var(--sc-green)}.sc-status strong.fail{color:var(--sc-red)}
@media(max-width:1150px){.sc-kpis{grid-template-columns:repeat(3,1fr)}.sc-kpi:nth-child(3){border-right:0}.sc-kpi:nth-child(-n+3){border-bottom:1px solid var(--sc-line)}.sc-detail-grid{grid-template-columns:repeat(3,1fr)}.sc-detail:nth-child(4n){border-right:1px solid var(--sc-line)}.sc-detail:nth-child(3n){border-right:0}}
@media(max-width:720px){.sycm-page{gap:12px}.sc-top{align-items:center}.sc-title h1{font-size:19px}.sc-title p{display:none}.sc-controlbar{grid-template-columns:1fr;padding:12px;gap:11px}.sc-periods{display:grid;grid-template-columns:repeat(4,1fr);padding:3px;border-radius:6px;background:color-mix(in srgb,var(--sc-card) 88%,var(--sc-line))}.sc-segment{height:34px;padding:0 5px}.sc-freshness{justify-self:start;text-align:left}.sc-kpis{grid-template-columns:repeat(2,1fr)}.sc-kpi{padding:14px}.sc-kpi:nth-child(3){border-right:1px solid var(--sc-line)}.sc-kpi:nth-child(even){border-right:0}.sc-kpi:nth-child(-n+4){border-bottom:1px solid var(--sc-line)}.sc-kpi-value{font-size:20px}.sc-tabs{width:100%;justify-content:space-between;gap:0}.sc-tab{font-size:12px}.sc-context{display:none}.sc-section{border-right:0;border-left:0;border-radius:0}.sc-table{white-space:normal}.sc-table th:nth-child(3),.sc-table td:nth-child(3),.sc-table th:nth-child(5),.sc-table td:nth-child(5){display:none}.sc-table th,.sc-table td{padding:11px 10px}.sc-table th:first-child,.sc-table td:first-child{min-width:145px}.sc-shop-id{max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sc-detail-grid{grid-template-columns:repeat(2,1fr)}.sc-detail:nth-child(3n){border-right:1px solid var(--sc-line)}.sc-detail:nth-child(even){border-right:0}.sc-status-list{grid-template-columns:1fr}.sc-section-head{padding:12px}.sc-section-head span{max-width:50%;text-align:right}}
</style>
