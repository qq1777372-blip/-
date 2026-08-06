<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { IonContent, IonIcon, IonPage, IonRefresher, IonRefresherContent, toastController } from '@ionic/vue'
import { hardwareChipOutline, refreshOutline, serverOutline, speedometerOutline } from 'ionicons/icons'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'

type Service = { name: string; display_name: string; active_state: string; sub_state: string; is_active: boolean }
type Status = {
  health: string
  hostname: string
  operating_system: string
  architecture: string
  cpu_count: number | null
  cpu_percent: number | null
  memory_used_bytes: number | null
  memory_total_bytes: number | null
  memory_percent: number | null
  disk_used_bytes: number | null
  disk_total_bytes: number | null
  disk_percent: number | null
  process_uptime_seconds: number | null
  database_count: number
  database_total_size_bytes: number | null
  database_connection_status: string
  database_latency_ms: number | null
  services: Service[]
}

const HEALTH: Record<string, { label: string; tone: string }> = {
  healthy: { label: '运行正常', tone: 'success' },
  warning: { label: '需要关注', tone: 'warning' },
  critical: { label: '存在异常', tone: 'danger' },
}
const SERVICE_STATE: Record<string, string> = {
  active: '已激活', inactive: '未激活', failed: '故障', activating: '启动中',
  deactivating: '停止中', reloading: '重载中', running: '运行中', exited: '已退出',
  dead: '已停止', listening: '监听中', waiting: '等待中', mounted: '已挂载',
}

const status = ref<Status | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const errorMessage = ref('')
const lastUpdated = ref<Date | null>(null)
// Guards against a slow earlier request landing after a newer one and
// overwriting fresher data.
let requestId = 0

const health = computed(() => HEALTH[status.value?.health || ''] || { label: '状态未知', tone: 'neutral' })
const activeServices = computed(() => status.value?.services.filter((item) => item.is_active).length || 0)
const updatedAt = computed(() => lastUpdated.value?.toLocaleTimeString('zh-CN', {
  hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
}) || '--')

function size(value: number | null) {
  if (value == null) return '--'
  if (value < 1024) return `${value} B`
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(value < 10 * 1024 ? 1 : 0)} KB`
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(value < 10 * 1024 ** 2 ? 1 : 0)} MB`
  return `${(value / 1024 ** 3).toFixed(1)} GB`
}
const percent = (value: number | null) => value == null ? '--' : `${Math.round(value * 10) / 10}%`
const barWidth = (value: number | null) => Math.min(100, Math.max(0, value ?? 0))
// Unknown stays its own state so the bar renders empty instead of looking healthy.
const barTone = (value: number | null) => value == null ? 'unknown' : value >= 90 ? 'danger' : value >= 75 ? 'warning' : 'normal'

function uptime(seconds: number | null) {
  if (seconds == null) return '--'
  const minutes = Math.floor(seconds / 60)
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor(minutes % 1440 / 60)
  const rest = minutes % 60
  if (days) return `${days} 天 ${hours} 小时`
  if (hours) return `${hours} 小时 ${rest} 分钟`
  return `${minutes} 分钟`
}

const dbLabel = (state: string) => ({ available: '正常', unavailable: '不可用', degraded: '受限' } as Record<string, string>)[state] || '未知'
const dbTone = (state: string) => state === 'available' ? 'good' : state === 'degraded' ? 'warn' : state === 'unavailable' ? 'bad' : 'muted'

function serviceDetail(service: Service) {
  const parts = [SERVICE_STATE[service.active_state], SERVICE_STATE[service.sub_state]].filter(Boolean)
  if (parts.length) return [...new Set(parts)].join(' · ')
  return service.is_active ? '服务已激活' : '服务未运行'
}
const serviceLabel = (service: Service) => service.is_active ? '正常' : service.active_state === 'failed' ? '故障' : '停止'
const serviceTone = (service: Service) => service.is_active ? 'good' : service.active_state === 'failed' ? 'bad' : 'muted'

async function toast(message: string) {
  const element = await toastController.create({ message, duration: 2200, color: 'danger' })
  await element.present()
}

async function load(force = false, event?: { target: { complete: () => void } }) {
  if (refreshing.value) {
    event?.target.complete()
    return
  }
  const current = ++requestId
  refreshing.value = true
  if (!status.value) loading.value = true
  try {
    const data = await api<Status>(`/dashboard/server-status${force ? '?refresh=true' : ''}`)
    if (current !== requestId) return
    status.value = data
    lastUpdated.value = new Date()
    errorMessage.value = ''
  } catch (error) {
    if (current !== requestId) return
    errorMessage.value = error instanceof ApiError ? error.detail : '服务器状态加载失败'
    // Only interrupt with a toast when stale data is already on screen; the
    // error panel covers the first-load case on its own.
    if (status.value) await toast(errorMessage.value)
  } finally {
    event?.target.complete()
    if (current === requestId) {
      refreshing.value = false
      loading.value = false
    }
  }
}

onMounted(() => load(!!status.value))
</script>

<template>
  <IonPage>
    <PageHeader title="服务器运行" subtitle="实时资源与服务状态" back />
    <IonContent>
      <IonRefresher slot="fixed" @ion-refresh="load(true, $event)"><IonRefresherContent /></IonRefresher>
      <main class="page-pad server-page">
        <section v-if="loading && !status" class="panel loading-panel" aria-live="polite">
          <span class="loading-orbit"><i /></span>
          <div><h2>正在获取服务器状态</h2><p>正在连接后台并读取运行数据…</p></div>
        </section>

        <section v-else-if="!status && errorMessage" class="panel error-panel">
          <span>!</span>
          <div><h2>暂时无法获取状态</h2><p>{{ errorMessage }}</p></div>
          <button :disabled="refreshing" @click="load(true)">{{ refreshing ? '重试中…' : '重新加载' }}</button>
        </section>

        <template v-else-if="status">
          <section class="panel host-card">
            <div class="host-top">
              <span :class="['health-badge', `health-${health.tone}`]"><i />{{ health.label }}</span>
              <button class="refresh-button" :disabled="refreshing" aria-label="刷新服务器状态" @click="load(true)">
                <IonIcon :icon="refreshOutline" :class="{ spinning: refreshing }" />
              </button>
            </div>
            <div class="host-main">
              <span class="host-icon"><IonIcon :icon="serverOutline" /></span>
              <div>
                <h1>{{ status.hostname || '服务器' }}</h1>
                <p>{{ [status.operating_system, status.architecture].filter(Boolean).join(' · ') || '系统信息未知' }}</p>
              </div>
            </div>
            <footer>
              <span>最后更新</span>
              <strong>{{ updatedAt }}</strong>
              <em v-if="errorMessage">刷新失败，当前为上次数据</em>
              <em v-else-if="refreshing">正在刷新…</em>
            </footer>
          </section>

          <section class="metric-strip server-metrics">
            <article class="metric">
              <span>CPU 使用率</span>
              <strong>{{ percent(status.cpu_percent) }}</strong>
              <small>{{ status.cpu_count ?? '--' }} 核心</small>
              <i class="usage-track"><b :class="barTone(status.cpu_percent)" :style="{ width: `${barWidth(status.cpu_percent)}%` }" /></i>
            </article>
            <article class="metric">
              <span>内存使用率</span>
              <strong>{{ percent(status.memory_percent) }}</strong>
              <small>{{ size(status.memory_used_bytes) }} / {{ size(status.memory_total_bytes) }}</small>
              <i class="usage-track"><b :class="barTone(status.memory_percent)" :style="{ width: `${barWidth(status.memory_percent)}%` }" /></i>
            </article>
            <article class="metric">
              <span>磁盘使用率</span>
              <strong>{{ percent(status.disk_percent) }}</strong>
              <small>{{ size(status.disk_used_bytes) }} / {{ size(status.disk_total_bytes) }}</small>
              <i class="usage-track"><b :class="barTone(status.disk_percent)" :style="{ width: `${barWidth(status.disk_percent)}%` }" /></i>
            </article>
          </section>

          <div class="section-title"><h2>运行概览</h2><span>核心状态</span></div>
          <section class="compact-list server-info">
            <article class="compact-row info-row">
              <span class="info-icon database"><IonIcon :icon="serverOutline" /></span>
              <div><h3>数据库</h3><p>{{ status.database_count }} 个库 · {{ size(status.database_total_size_bytes) }}</p></div>
              <strong :class="['state-label', dbTone(status.database_connection_status)]">{{ dbLabel(status.database_connection_status) }}</strong>
            </article>
            <article class="compact-row info-row">
              <span class="info-icon latency"><IonIcon :icon="speedometerOutline" /></span>
              <div><h3>接口延迟</h3><p>主数据库连接响应</p></div>
              <strong>{{ status.database_latency_ms === null ? '--' : `${Math.round(status.database_latency_ms * 10) / 10} ms` }}</strong>
            </article>
            <article class="compact-row info-row">
              <span class="info-icon uptime"><IonIcon :icon="speedometerOutline" /></span>
              <div><h3>应用运行</h3><p>当前后台进程持续时间</p></div>
              <strong>{{ uptime(status.process_uptime_seconds) }}</strong>
            </article>
          </section>

          <div class="section-title service-title">
            <h2>服务状态</h2>
            <span>正常 {{ activeServices }} / 共 {{ status.services.length }}</span>
          </div>
          <section class="compact-list service-list">
            <article v-for="service in status.services" :key="service.name" class="compact-row service-row">
              <i :class="['service-dot', serviceTone(service)]" />
              <div><h3>{{ service.display_name || service.name }}</h3><p>{{ serviceDetail(service) }}</p></div>
              <strong :class="['state-label', serviceTone(service)]">{{ serviceLabel(service) }}</strong>
            </article>
            <div v-if="!status.services.length" class="empty-state service-empty">
              <IonIcon :icon="hardwareChipOutline" />
              <span>暂无服务状态数据</span>
            </div>
          </section>
        </template>
      </main>
    </IonContent>
  </IonPage>
</template>

<style scoped>
.server-page{display:grid;gap:12px}
.loading-panel,.error-panel{min-height:132px;display:flex;align-items:center;gap:14px;padding:20px}
.loading-panel h2,.loading-panel p,.error-panel h2,.error-panel p{margin:0}
.loading-panel h2,.error-panel h2{font-size:16px}
.loading-panel p,.error-panel p{margin-top:5px;color:var(--app-muted);font-size:11px;line-height:1.5}
.loading-orbit{width:42px;height:42px;flex:none;border-radius:50%;display:grid;place-items:center;background:color-mix(in srgb,var(--app-blue) 12%,var(--app-card))}
.loading-orbit i{width:20px;height:20px;border:2px solid color-mix(in srgb,var(--app-blue) 25%,transparent);border-top-color:var(--app-blue);border-radius:50%;animation:spin .8s linear infinite}
.error-panel{display:grid;grid-template-columns:38px minmax(0,1fr);align-items:center}
.error-panel>span{width:36px;height:36px;border-radius:11px;display:grid;place-items:center;color:#dc2626;background:color-mix(in srgb,#ef4444 12%,var(--app-card));font-weight:800}
.error-panel button{grid-column:2;justify-self:start;padding:8px 13px;border:0;border-radius:9px;color:#fff;background:var(--app-blue);font-weight:650}
.error-panel button:disabled{opacity:.55}
.host-card{padding:14px}
.host-top{display:flex;align-items:center;justify-content:space-between}
.health-badge{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:999px;font-size:11px;font-weight:700}
.health-badge i{width:6px;height:6px;border-radius:50%;background:currentColor}
.health-success{color:#15803d;background:color-mix(in srgb,#22c55e 14%,var(--app-card))}
.health-warning{color:#b45309;background:color-mix(in srgb,#f59e0b 15%,var(--app-card))}
.health-danger{color:#dc2626;background:color-mix(in srgb,#ef4444 14%,var(--app-card))}
.health-neutral{color:var(--app-muted);background:color-mix(in srgb,var(--app-muted) 12%,var(--app-card))}
.refresh-button{width:44px;height:44px;margin:-7px -7px -7px 0;padding:0;border:0;border-radius:50%;display:grid;place-items:center;color:var(--app-blue);background:transparent}
.refresh-button:active{background:color-mix(in srgb,var(--app-blue) 10%,transparent)}
.refresh-button:disabled{opacity:.55}
.refresh-button ion-icon{font-size:21px}
.refresh-button .spinning{animation:spin .8s linear infinite}
.host-main{display:grid;grid-template-columns:48px minmax(0,1fr);gap:12px;align-items:center;margin-top:10px}
.host-icon{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;color:var(--app-blue);background:color-mix(in srgb,var(--app-blue) 12%,var(--app-card))}
.host-icon ion-icon{font-size:25px}
.host-main h1,.host-main p{margin:0;overflow:hidden;text-overflow:ellipsis}
.host-main h1{white-space:nowrap;font-size:20px}
.host-main p{margin-top:5px;color:var(--app-muted);font-size:11px;line-height:1.45}
.host-card footer{min-height:25px;display:flex;align-items:end;gap:7px;margin-top:12px;padding-top:10px;border-top:1px solid var(--app-line);font-size:10px}
.host-card footer span{color:var(--app-muted)}
.host-card footer strong{font-size:11px}
.host-card footer em{margin-left:auto;color:#b45309;font-style:normal;text-align:right}
.server-metrics .metric{min-width:0}
.server-metrics small{display:block;margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--app-muted);font-size:9px}
.usage-track{height:4px;display:block;overflow:hidden;margin-top:9px;border-radius:999px;background:color-mix(in srgb,var(--app-line) 88%,transparent)}
.usage-track b{height:100%;display:block;border-radius:inherit;background:var(--app-blue);transition:width .35s ease}
.usage-track b.warning{background:#f59e0b}
.usage-track b.danger{background:#ef4444}
.usage-track b.unknown{width:0!important}
.section-title{margin-bottom:-3px}
.info-row{grid-template-columns:40px minmax(0,1fr) auto}
.info-icon{width:36px;height:36px;border-radius:11px;display:grid;place-items:center}
.info-icon ion-icon{font-size:19px}
.info-icon.database{color:#2563eb;background:color-mix(in srgb,#3b82f6 12%,var(--app-card))}
.info-icon.latency{color:#7c3aed;background:color-mix(in srgb,#8b5cf6 12%,var(--app-card))}
.info-icon.uptime{color:#0891b2;background:color-mix(in srgb,#06b6d4 12%,var(--app-card))}
.info-row>div,.service-row>div{min-width:0}
.info-row>strong{color:var(--app-text);font-size:12px;white-space:nowrap}
.state-label{padding:4px 8px;border-radius:999px;font-size:10px!important}
.state-label.good{color:#15803d;background:color-mix(in srgb,#22c55e 13%,var(--app-card))}
.state-label.warn{color:#b45309;background:color-mix(in srgb,#f59e0b 14%,var(--app-card))}
.state-label.bad{color:#dc2626;background:color-mix(in srgb,#ef4444 13%,var(--app-card))}
.state-label.muted{color:var(--app-muted);background:color-mix(in srgb,var(--app-muted) 10%,var(--app-card))}
.service-title{margin-top:5px}
.service-row{grid-template-columns:10px minmax(0,1fr) auto;padding-left:15px}
.service-dot{width:8px;height:8px;border-radius:50%;background:var(--app-muted)}
.service-dot.good{background:#22c55e;box-shadow:0 0 0 4px color-mix(in srgb,#22c55e 12%,transparent)}
.service-dot.bad{background:#ef4444;box-shadow:0 0 0 4px color-mix(in srgb,#ef4444 12%,transparent)}
.service-row h3,.service-row p{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.service-empty{display:flex;flex-direction:column;align-items:center;gap:8px}
.service-empty ion-icon{font-size:27px}
.ion-palette-dark .health-success,.ion-palette-dark .state-label.good{color:#4ade80}
.ion-palette-dark .health-warning,.ion-palette-dark .state-label.warn{color:#fbbf24}
.ion-palette-dark .health-danger,.ion-palette-dark .state-label.bad{color:#fb7185}
.ion-palette-dark .error-panel>span{color:#fb7185}
.ion-palette-dark .info-icon.database{color:#60a5fa}
.ion-palette-dark .info-icon.latency{color:#a78bfa}
.ion-palette-dark .info-icon.uptime{color:#22d3ee}
@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:380px){
.server-page{padding-inline:9px}
.host-main{grid-template-columns:42px minmax(0,1fr);gap:10px}
.host-icon{width:42px;height:42px}
.host-main h1{font-size:18px}
.host-card footer{flex-wrap:wrap}
.host-card footer em{width:100%;margin-left:0;text-align:left}
.server-metrics{grid-auto-columns:minmax(108px,42%)}
.info-row{grid-template-columns:36px minmax(0,1fr) auto;padding-inline:10px}
.info-icon{width:33px;height:33px}
.info-row>strong{max-width:88px;overflow:hidden;text-overflow:ellipsis}
.service-row{padding-inline:12px 10px}
.state-label{padding-inline:6px}
}
@media(prefers-reduced-motion:reduce){
.loading-orbit i,.refresh-button .spinning{animation-duration:1.8s}
.usage-track b{transition:none}
}
</style>
