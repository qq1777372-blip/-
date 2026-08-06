<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { IonButton, IonContent, IonIcon, IonPage, IonRefresher, IonRefresherContent, toastController } from '@ionic/vue'
import { syncOutline } from 'ionicons/icons'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'

type Snapshot = { id: number; shopId: string; shopName: string; collectedAt: string; receivedAt: string; uv: number | null; pv: number | null; cartByrCnt: number | null; payByrCnt: number | null; payAmt: number | null; payRate: number | null }
type SyncRequest = { id: number; status: 'pending' | 'running' | 'completed' | 'failed'; error: string }
const shops = ref<Snapshot[]>([])
const history = ref<Snapshot[]>([])
const selectedShop = ref('')
const loading = ref(true)
const syncing = ref(false)
const syncStatus = ref('')
const selected = computed(() => shops.value.find((item) => item.shopId === selectedShop.value) || shops.value[0])
const number = (value: number | null) => value == null ? '--' : new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)
const money = (value: number | null) => value == null ? '--' : `¥${number(value)}`
const percent = (value: number | null) => value == null ? '--' : `${(value * 100).toFixed(2)}%`
const time = (value: string) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '--'

async function loadHistory() {
  history.value = selectedShop.value ? await api<Snapshot[]>(`/api/sycm/shops/${encodeURIComponent(selectedShop.value)}/snapshots?limit=100`) : []
}
async function load(event?: { target: { complete: () => void } }) {
  try {
    shops.value = await api<Snapshot[]>('/api/sycm/latest')
    if (!selectedShop.value && shops.value.length) selectedShop.value = shops.value[0].shopId
    await loadHistory()
  } catch (error) {
    const toast = await toastController.create({ message: error instanceof ApiError ? error.detail : '生意参谋数据加载失败', duration: 2200, color: 'danger' })
    await toast.present()
  } finally { loading.value = false; event?.target.complete() }
}
const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))
async function syncData() {
  if (syncing.value) return
  syncing.value = true
  syncStatus.value = '正在提交同步请求'
  try {
    const task = await api<SyncRequest>('/api/sycm/sync-requests', { method: 'POST' })
    for (let attempt = 0; attempt < 90; attempt += 1) {
      const current = await api<SyncRequest | null>('/api/sycm/sync-requests/latest')
      if (current?.id === task.id && current.status === 'completed') {
        syncStatus.value = '同步完成'
        await load()
        const toast = await toastController.create({ message: '店铺数据已同步', duration: 1800, color: 'success' })
        await toast.present()
        return
      }
      if (current?.id === task.id && current.status === 'failed') throw new Error(current.error || '采集端同步失败')
      syncStatus.value = current?.status === 'running' ? '采集端正在同步' : '等待采集端'
      await wait(2000)
    }
    syncStatus.value = '请求已提交，请稍后下拉刷新'
  } catch (error) {
    syncStatus.value = '同步失败'
    const message = error instanceof ApiError ? error.detail : error instanceof Error ? error.message : '同步请求失败'
    const toast = await toastController.create({ message, duration: 2200, color: 'danger' })
    await toast.present()
  } finally { syncing.value = false }
}
onMounted(() => load())
</script>

<template>
  <IonPage>
    <PageHeader title="生意参谋" subtitle="店铺经营数据与采集历史" back />
    <IonContent>
      <IonRefresher slot="fixed" @ion-refresh="load"><IonRefresherContent /></IonRefresher>
      <main class="page-pad sycm-page">
        <div class="toolbar">
          <label>店铺</label>
          <select v-model="selectedShop" @change="loadHistory"><option v-for="shop in shops" :key="shop.shopId" :value="shop.shopId">{{ shop.shopName }}</option></select>
          <IonButton size="small" :disabled="syncing" @click="syncData"><IonIcon slot="start" :icon="syncOutline" />{{ syncing ? '同步中' : '同步数据' }}</IonButton>
          <span>{{ syncStatus || (selected ? `更新于 ${time(selected.collectedAt)}` : '等待客户端上传') }}</span>
        </div>
        <section v-if="selected" class="metrics">
          <div><small>访客数</small><strong>{{ number(selected.uv) }}</strong></div><div><small>浏览量</small><strong>{{ number(selected.pv) }}</strong></div>
          <div><small>加购人数</small><strong>{{ number(selected.cartByrCnt) }}</strong></div><div><small>支付买家数</small><strong>{{ number(selected.payByrCnt) }}</strong></div>
          <div><small>支付金额</small><strong>{{ money(selected.payAmt) }}</strong></div><div><small>支付转化率</small><strong>{{ percent(selected.payRate) }}</strong></div>
        </section>
        <section class="history">
          <header><h2>采集历史</h2><span>{{ history.length }} 条</span></header>
          <div class="table-wrap"><table><thead><tr><th>采集时间</th><th>访客</th><th>浏览量</th><th>加购</th><th>支付买家</th><th>支付金额</th><th>转化率</th></tr></thead><tbody><tr v-for="item in history" :key="item.id"><td>{{ time(item.collectedAt) }}</td><td>{{ number(item.uv) }}</td><td>{{ number(item.pv) }}</td><td>{{ number(item.cartByrCnt) }}</td><td>{{ number(item.payByrCnt) }}</td><td>{{ money(item.payAmt) }}</td><td>{{ percent(item.payRate) }}</td></tr></tbody></table></div>
          <div v-if="!loading && !history.length" class="empty-state">暂无采集数据</div>
        </section>
      </main>
    </IonContent>
  </IonPage>
</template>

<style scoped>
.sycm-page{display:grid;gap:16px}.toolbar{display:grid;grid-template-columns:auto minmax(180px,320px) 1fr;gap:10px;align-items:center}.toolbar label{font-size:12px;font-weight:700}.toolbar select{height:38px;padding:0 10px;border:1px solid var(--app-line);border-radius:6px;color:var(--app-text);background:var(--app-card)}.toolbar span{color:var(--app-muted);font-size:11px;text-align:right}.metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid var(--app-line);border-radius:8px;background:var(--app-card)}.metrics div{min-width:0;padding:16px}.metrics div+div{border-left:1px solid var(--app-line)}.metrics small,.metrics strong{display:block}.metrics small{color:var(--app-muted);font-size:11px}.metrics strong{margin-top:7px;font-size:21px}.history{min-width:0}.history header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}.history h2{margin:0;font-size:15px}.history header span{color:var(--app-muted);font-size:11px}.table-wrap{overflow:auto;border:1px solid var(--app-line);border-radius:8px;background:var(--app-card)}table{width:100%;min-width:760px;border-collapse:collapse}th,td{padding:11px 12px;border-bottom:1px solid var(--app-line);font-size:12px;text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{color:var(--app-muted);font-weight:600;background:var(--ion-background-color)}tbody tr:last-child td{border-bottom:0}@media(max-width:800px){.toolbar{grid-template-columns:auto 1fr}.toolbar span{grid-column:1/-1;text-align:left}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.metrics div+div{border-left:0}.metrics div:nth-child(even){border-left:1px solid var(--app-line)}.metrics div:nth-child(n+3){border-top:1px solid var(--app-line)}}
.toolbar{grid-template-columns:auto minmax(180px,320px) auto 1fr}.toolbar ion-button{margin:0}@media(max-width:800px){.toolbar{grid-template-columns:auto 1fr auto}}
</style>
