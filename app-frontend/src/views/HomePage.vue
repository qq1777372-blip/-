<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { IonContent, IonIcon, IonPage, onIonViewWillEnter } from '@ionic/vue'
import { appsOutline, createOutline, refreshOutline } from 'ionicons/icons'
import { useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { api } from '../api'
import { readCache, syncedLabel, writeCache } from '../dataCache'
import { network } from '../network'
import { can, session } from '../session'
import { appModules, canOpenModule } from '../modules'
import { defaultHomeKeys, maxHomeModules, readHomeKeys, resolveHomeModules, writeHomeKeys } from '../homeModules'

type Summary = Record<string, number>
type Month = { month: string; total_profit: number }
const router = useRouter()
const warehouse = ref<Summary | null>(null)
const tasks = ref<Summary | null>(null)
const expenses = ref<Summary | null>(null)
const profits = ref<Summary | null>(null)
const months = ref<Month[]>([])
const loading = ref(false)
const failed = ref(false)
const configuring = ref(false)
const monthsLoaded = ref(false)
const cachedAt = ref<number | null>(null)
let loadId = 0
const homeKeys = ref(readHomeKeys())
const permittedModules = computed(() => appModules.filter((item) => canOpenModule(item, session.user?.role, can)))
const visibleModules = computed(() => resolveHomeModules(homeKeys.value, session.user?.role, can))
const configOptions = computed(() => permittedModules.value.filter((item) => item.key !== 'company-expenses' || can('task_bookkeeping')))
const money = (value?: number) => value == null ? '--' : `¥${Math.round(value * 100) / 100}`
const count = (value?: number) => value == null ? '--' : value
const chartMonths = computed(() => months.value.slice(0, 6).reverse())
const currentMonthKey = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit' }).format(new Date()).slice(0, 7)
// Only show 0 once the monthly API actually succeeded; on failure show --, so a
// dead request never looks like a real month with no profit.
const currentMonthProfit = computed(() => (monthsLoaded.value ? (months.value.find((item) => item.month === currentMonthKey)?.total_profit ?? 0) : undefined))
const syncStatus = computed(() => {
  if (loading.value) return '同步中…'
  if (!network.online || session.offline) return cachedAt.value ? `离线 · ${syncedLabel(cachedAt.value)}` : '当前离线'
  if (failed.value && cachedAt.value) return `部分数据不可用 · ${syncedLabel(cachedAt.value)}`
  return '实时同步'
})
const maxProfit = computed(() => Math.max(...chartMonths.value.map((item) => Math.abs(item.total_profit)), 1))

type HomeCache = { warehouse: Summary | null; tasks: Summary | null; expenses: Summary | null; profits: Summary | null; months: Month[] }
const cacheKey = 'home-summary'

function hydrateCache() {
  const cached = readCache<HomeCache>(session.user?.id, cacheKey)
  if (!cached) return false
  warehouse.value = cached.data.warehouse
  tasks.value = cached.data.tasks
  expenses.value = cached.data.expenses
  profits.value = cached.data.profits
  months.value = cached.data.months
  monthsLoaded.value = true
  cachedAt.value = cached.savedAt
  return true
}

function persistCache() {
  writeCache<HomeCache>(session.user?.id, cacheKey, {
    warehouse: warehouse.value,
    tasks: tasks.value,
    expenses: expenses.value,
    profits: profits.value,
    months: months.value,
  })
  cachedAt.value = Date.now()
}

async function loadSummary() {
  const currentLoad = ++loadId
  const hadCache = hydrateCache()
  loading.value = true
  failed.value = false
  const requests = await Promise.allSettled([
    api<Summary>('/warehouse/summary'),
    api<Summary>('/task-bookkeeping/summary'),
    api<Summary>('/company-expenses/summary'),
    api<Summary>('/dingtalk-profits/summary'),
    api<Month[]>('/dingtalk-profits/monthly-summary'),
  ])
  // A visibility refresh may finish after a newer Ionic-entry refresh. Ignore the
  // stale result so it cannot overwrite fresher data.
  if (currentLoad !== loadId) return
  if (requests[0].status === 'fulfilled') warehouse.value = requests[0].value
  if (requests[1].status === 'fulfilled') tasks.value = requests[1].value
  if (requests[2].status === 'fulfilled') expenses.value = requests[2].value
  if (requests[3].status === 'fulfilled') profits.value = requests[3].value
  if (requests[4].status === 'fulfilled') {
    months.value = requests[4].value
    monthsLoaded.value = true
  } else if (!hadCache) {
    months.value = []
    monthsLoaded.value = false
  }
  failed.value = requests.some((item) => item.status === 'rejected')
  if (requests.some((item) => item.status === 'fulfilled')) persistCache()
  loading.value = false
}

function toggleModule(key: string) {
  const next = homeKeys.value.includes(key)
    ? homeKeys.value.filter((item) => item !== key)
    : [...homeKeys.value, key]
  if (!next.length || next.length > maxHomeModules) return
  homeKeys.value = next
  writeHomeKeys(next)
}
function resetModules() {
  homeKeys.value = [...defaultHomeKeys]
  writeHomeKeys(homeKeys.value)
}

function refreshWhenVisible() {
  if (document.visibilityState === 'visible') void loadSummary()
}
onIonViewWillEnter(loadSummary)
onMounted(() => document.addEventListener('visibilitychange', refreshWhenVisible))
onUnmounted(() => document.removeEventListener('visibilitychange', refreshWhenVisible))
</script>

<template>
  <IonPage>
    <PageHeader title="首页" hide-avatar />
    <IonContent>
      <main class="native-home">
        <div class="home-heading">
          <div><h2>常用功能</h2><small v-if="configuring">选择要显示在首页的功能</small></div>
          <button v-if="!configuring" @click="configuring = true"><IonIcon :icon="createOutline" />自定义</button>
          <div v-else class="home-config-actions"><button @click="resetModules">恢复默认</button><button @click="configuring = false">完成</button></div>
        </div>
        <section v-if="!configuring" class="home-functions">
          <button v-for="item in visibleModules" :key="item.key" @click="router.push(item.route)"><span :style="{ background: `${item.color}15`, color: item.color }"><IonIcon :icon="item.icon" /></span><b>{{ item.title }}</b></button>
          <button @click="router.push('/tabs/workbench')"><span class="all-functions"><IonIcon :icon="appsOutline" /></span><b>全部功能</b></button>
        </section>
        <section v-else class="home-function-picker">
          <button v-for="item in configOptions" :key="item.key" :class="{ selected: homeKeys.includes(item.key) }" @click="toggleModule(item.key)"><span :style="{ background: `${item.color}15`, color: item.color }"><IonIcon :icon="item.icon" /></span><b>{{ item.title }}</b><i>{{ homeKeys.includes(item.key) ? '已显示' : '添加' }}</i></button>
        </section>

        <div class="home-heading"><h2>经营数据</h2><button v-if="failed && network.online" class="sync-error" @click="loadSummary"><IonIcon :icon="refreshOutline" />同步失败，重试</button><span v-else>{{ syncStatus }}</span></div>
        <section class="business-board">
          <div class="business-grid"><div><small>公司消费</small><b>{{ money(expenses?.month_total) }}</b></div><div><small>累计利润</small><b>{{ money(profits?.total_profit) }}</b></div><div><small>当月钉钉利润</small><b>{{ money(currentMonthProfit) }}</b></div><div><small>待签收</small><b>{{ count(tasks?.pending_signed_count) }}</b></div><div><small>库存数量</small><b>{{ count(warehouse?.total_quantity) }}</b></div><div><small>库存成本</small><b>{{ money(warehouse?.total_cost) }}</b></div></div>
          <button class="trend-head" @click="router.push('/tabs/list/profits')"><span>钉钉月度利润</span><em>查看趋势 ›</em></button>
          <div v-if="chartMonths.length" class="mini-chart"><div v-for="item in chartMonths" :key="item.month"><span :style="{ height: `${Math.max(Math.abs(item.total_profit) / maxProfit * 58, 5)}px` }" :class="{ negative: item.total_profit < 0 }"></span><small>{{ item.month.slice(5) }}月</small></div></div><div v-else class="chart-empty">{{ loading ? '正在加载趋势…' : failed ? '趋势数据暂不可用' : '暂无趋势数据' }}</div>
        </section>

        <div class="home-heading"><h2>待办提醒</h2><button @click="router.push('/tabs/tasks')">查看全部</button></div><section class="home-todos"><button @click="router.push('/tabs/list/tasks')"><i class="orange"></i><span><b>待签收任务</b><small>需要及时跟进任务状态</small></span><strong>{{ count(tasks?.pending_signed_count) }}</strong></button><button @click="router.push('/tabs/list/tasks')"><i class="red"></i><span><b>待结算任务</b><small>需要处理回款与结算</small></span><strong>{{ count(tasks?.pending_settlement_count) }}</strong></button><button @click="router.push('/tabs/module/warehouse?tab=stocks')"><i class="blue"></i><span><b>库存预警</b><small>可用库存已达到预警值</small></span><strong>{{ count(warehouse?.low_stock_count) }}</strong></button></section>
      </main>
    </IonContent>
  </IonPage>
</template>

<style scoped>
.native-home{padding:12px 14px 92px}.home-heading{display:flex;justify-content:space-between;align-items:center;margin:12px 2px 8px}.home-heading h2{margin:0;font-size:16px}.home-heading>div:first-child{min-width:0}.home-heading small{display:block;margin-top:3px;color:var(--app-muted);font-size:10px}.home-heading button,.home-heading span{display:flex;align-items:center;gap:3px;border:0;color:var(--app-muted);background:transparent;font-size:11px}.home-heading button ion-icon{font-size:14px}.home-config-actions{display:flex;gap:5px}.home-config-actions button:last-child{color:#1677ff;font-weight:700}.home-functions{display:grid;grid-template-columns:repeat(4,1fr);gap:17px 7px;padding:15px 8px;border-radius:14px;background:var(--app-card)}.home-functions button,.home-function-picker button{min-width:0;padding:0;border:0;color:var(--app-text);background:transparent}.home-functions span,.home-function-picker span{width:45px;height:45px;margin:auto;display:grid;place-items:center;border-radius:14px}.home-functions .all-functions{color:#64748b;background:#edf1f7}.home-functions ion-icon,.home-function-picker ion-icon{font-size:23px}.home-functions b,.home-function-picker b{display:block;margin-top:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px}.home-function-picker{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:12px 8px;border:1px solid var(--app-line);border-radius:14px;background:var(--app-card)}.home-function-picker button{position:relative;padding:8px 3px 10px;border:1px solid transparent;border-radius:12px}.home-function-picker button.selected{border-color:#93b4ff;background:#eff5ff}.home-function-picker i{display:block;margin-top:4px;color:var(--app-muted);font-size:10px;font-style:normal}.home-function-picker .selected i{color:#1677ff}.business-board{overflow:hidden;border-radius:14px;background:var(--app-card)}.business-grid{display:grid;grid-template-columns:repeat(3,1fr)}.business-grid div{padding:13px 11px;border-right:1px solid var(--app-line);border-bottom:1px solid var(--app-line)}.business-grid div:nth-child(3n){border-right:0}.business-grid small,.business-grid b{display:block}.business-grid small{color:var(--app-muted);font-size:10px}.business-grid b{margin-top:7px;font-size:17px}.trend-head{width:100%;display:flex;justify-content:space-between;padding:12px 12px 3px;border:0;color:var(--app-text);background:transparent}.trend-head span{font-weight:700}.trend-head em{color:var(--app-blue);font-style:normal;font-size:11px}.mini-chart{height:92px;display:flex;align-items:end;gap:11px;padding:4px 13px 11px}.mini-chart>div{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:end;gap:5px}.mini-chart span{width:18px;min-height:5px;border-radius:5px 5px 2px 2px;background:#1991ff}.mini-chart span.negative{background:#ef4444}.mini-chart small{color:var(--app-muted);font-size:9px}.home-todos{overflow:hidden;border-radius:14px;background:var(--app-card)}.home-todos button{width:100%;display:grid;grid-template-columns:8px 1fr auto;gap:10px;align-items:center;padding:12px;border:0;border-bottom:1px solid var(--app-line);text-align:left;color:var(--app-text);background:transparent}.home-todos button:last-child{border-bottom:0}.home-todos i{width:7px;height:7px;border-radius:50%}.orange{background:#f59e0b}.red{background:#ef4444}.blue{background:#1991ff}.home-todos b,.home-todos small{display:block}.home-todos b{font-size:13px}.home-todos small{margin-top:3px;color:var(--app-muted);font-size:10px}.home-todos strong{font-size:18px}.ion-palette-dark .home-functions .all-functions{background:#1d2939}.ion-palette-dark .home-function-picker button.selected{background:#12233d}
</style>
