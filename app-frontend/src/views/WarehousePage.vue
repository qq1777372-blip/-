<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { IonContent, IonIcon, IonPage, IonRefresher, IonRefresherContent, IonSearchbar, alertController, toastController } from '@ionic/vue'
import { addOutline, arrowForwardOutline, refreshOutline } from 'ionicons/icons'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'
import { amount } from '../expenses'
import { session } from '../session'

type Row = Record<string, any>
type Tab = 'stocks' | 'warehouses' | 'products' | 'inbound' | 'outbound' | 'movements'
const router = useRouter()
const route = useRoute()
const summary = ref<Record<string, number>>({})
const data = ref<Record<Tab, Row[]>>({ stocks: [], warehouses: [], products: [], inbound: [], outbound: [], movements: [] })
const tab = ref<Tab>('stocks')
const query = ref('')
const warehouseFilter = ref('')
const statusFilter = ref('')
const labels: Record<Tab, string> = { stocks: '库存', warehouses: '仓库', products: '商品', inbound: '入库', outbound: '出库', movements: '流水' }
const statusLabels: Record<string, string> = { pending: '待拣货', picking: '拣货中', checked: '已复核', packed: '已打包', shipped: '已发货', cancelled: '已取消', completed: '已完成' }
const nextStatus: Record<string, string> = { pending: 'picking', picking: 'checked', checked: 'packed', packed: 'shipped' }
const rows = computed(() => data.value[tab.value].filter((row) => { const keyword=query.value.trim().toLowerCase(); return (!keyword||Object.values(row).join(' ').toLowerCase().includes(keyword))&&(!warehouseFilter.value||String(row.warehouse_id)===warehouseFilter.value)&&(!statusFilter.value||row.status===statusFilter.value) }))
const canWrite = computed(() => ['superadmin', 'admin', 'super_admin', 'editor'].includes(session.user?.role || ''))
const canCreate = computed(() => canWrite.value && ['warehouses', 'products', 'inbound', 'outbound'].includes(tab.value))
const validTabs = new Set<Tab>(['stocks', 'warehouses', 'products', 'inbound', 'outbound', 'movements'])
watch(() => route.query.tab, (value) => { const requested = String(value || 'stocks') as Tab; tab.value = validTabs.has(requested) ? requested : 'stocks' }, { immediate: true })

async function load(event?: { target: { complete: () => void } }) {
  try {
    const [summaryResult, warehouses, products, stocks, inbound, outbound, movements] = await Promise.all([
      api<Record<string, number>>('/warehouse/summary'), api<Row[]>('/warehouse/warehouses'), api<Row[]>('/warehouse/products'),
      api<Row[]>('/warehouse/stocks'), api<Row[]>('/warehouse/inbound-orders'), api<Row[]>('/warehouse/outbound-orders'), api<Row[]>('/warehouse/movements'),
    ])
    summary.value = summaryResult
    data.value = { warehouses, products, stocks, inbound, outbound, movements }
  } catch (error) {
    const toast = await toastController.create({ message: error instanceof ApiError ? error.detail : '仓储数据加载失败', duration: 2200, color: 'danger' })
    await toast.present()
  } finally { event?.target.complete() }
}

function title(row: Row) {
  return row.product_name || row.name || row.order_no || row.sku || row.warehouse_name || row.movement_type || '仓储记录'
}
function subtitle(row: Row) {
  return [row.sku, row.code, row.warehouse_name, row.supplier, row.recipient_name, row.reference_no].filter(Boolean).join(' · ') || row.remark || '—'
}
function value(row: Row) {
  if (tab.value === 'stocks') return `${row.available_quantity ?? 0} ${row.unit || '件'}`
  if (tab.value === 'movements') return `${Number(row.quantity_change) > 0 ? '+' : ''}${row.quantity_change ?? 0}`
  if (tab.value === 'outbound' || tab.value === 'inbound') return statusLabels[row.status] || row.status
  if (tab.value === 'products') return amount(row.cost_price || 0)
  return row.is_active === false ? '停用' : '启用'
}
function openCreate() { router.push(`/tabs/warehouse/form/${tab.value === 'warehouses' ? 'warehouse' : tab.value === 'products' ? 'product' : tab.value}`) }
function openRow(row: Row) {
  if (!canWrite.value) return
  if (tab.value === 'warehouses') router.push(`/tabs/warehouse/form/warehouse/${row.id}`)
  if (tab.value === 'products') router.push(`/tabs/warehouse/form/product/${row.id}`)
  if (tab.value === 'inbound' && row.status === 'completed') router.push(`/tabs/warehouse/form/inbound/${row.id}`)
}

async function cancelInbound(row: Row) { const alert=await alertController.create({header:'撤销入库单',message:`撤销 ${row.order_no} 后会冲回库存，确定继续吗？`,buttons:['取消',{text:'确认撤销',role:'destructive',handler:async()=>{try{await api(`/warehouse/inbound-orders/${row.id}`,{method:'DELETE'});await load()}catch(error){const toast=await toastController.create({message:error instanceof ApiError?error.detail:'撤销失败',duration:2200,color:'danger'});await toast.present()}}}]});await alert.present() }

async function updateOutbound(order: Row, status: string) {
  const payload: Record<string, string> = { status }
  if (status === 'shipped' && order.delivery_method === 'shipping') {
    const alert = await alertController.create({
      header: '确认发货',
      inputs: [
        { name: 'carrier', placeholder: '快递公司', value: order.carrier || '' },
        { name: 'tracking_no', placeholder: '物流单号', value: order.tracking_no || '' },
      ],
      buttons: [{ text: '取消', role: 'cancel' }, { text: '确认发货', role: 'confirm' }],
    })
    await alert.present()
    const result = await alert.onDidDismiss()
    if (result.role !== 'confirm') return
    payload.carrier = result.data.values.carrier
    payload.tracking_no = result.data.values.tracking_no
  }
  try {
    await api(`/warehouse/outbound-orders/${order.id}/status`, { method: 'PATCH', body: JSON.stringify(payload) })
    await load()
  } catch (error) {
    const toast = await toastController.create({ message: error instanceof ApiError ? error.detail : '状态更新失败', duration: 2200, color: 'danger' })
    await toast.present()
  }
}

onMounted(load)
</script>

<template>
  <IonPage><PageHeader title="仓储管理" subtitle="库存、出入库和流水" back />
    <IonContent><IonRefresher slot="fixed" @ion-refresh="load"><IonRefresherContent /></IonRefresher>
      <main class="page-pad warehouse-page">
        <section class="metric-strip">
          <article class="metric"><span>库存数量</span><strong>{{ summary.total_quantity || 0 }} 件</strong></article>
          <article class="metric"><span>库存成本</span><strong>{{ amount(summary.total_cost || 0) }}</strong></article>
          <article class="metric"><span>库存预警</span><strong>{{ summary.low_stock_count || 0 }} 项</strong></article>
          <article class="metric"><span>待出库</span><strong>{{ summary.pending_outbound_count || 0 }} 单</strong></article>
          <article class="metric"><span>今日入库 / 出库</span><strong>{{ summary.today_inbound_quantity || 0 }} / {{ summary.today_outbound_quantity || 0 }}</strong></article>
        </section>
        <nav class="warehouse-tabs"><button v-for="key in (Object.keys(labels) as Tab[])" :key="key" :class="{ active: tab === key }" @click="tab = key">{{ labels[key] }}</button></nav>
        <IonSearchbar v-model="query" placeholder="搜索商品、单号、仓库或物流" mode="ios" />
        <div class="warehouse-filters"><select v-model="warehouseFilter"><option value="">全部仓库</option><option v-for="item in data.warehouses" :key="item.id" :value="String(item.id)">{{ item.name }}</option></select><select v-if="tab==='outbound'||tab==='inbound'" v-model="statusFilter"><option value="">全部状态</option><option v-for="(label,key) in statusLabels" :key="key" :value="key">{{ label }}</option></select></div>
        <div class="list-toolbar"><b>{{ labels[tab] }}记录</b><button v-if="canCreate" @click="openCreate"><IonIcon :icon="addOutline" />新增</button><button v-else @click="() => load()"><IonIcon :icon="refreshOutline" />刷新</button></div>
        <section class="compact-list warehouse-list">
          <article v-for="(row, index) in rows" :key="String(row.id || index)" class="warehouse-row" @click="openRow(row)">
            <span class="warehouse-icon"><img v-if="row.image_url" :src="row.image_url" alt="" /><template v-else>{{ labels[tab].slice(0, 1) }}</template></span>
            <div class="warehouse-main"><h3>{{ title(row) }}</h3><p>{{ subtitle(row) }}</p><small v-if="row.created_at">{{ String(row.created_at).replace('T', ' ').slice(0, 16) }}</small><small v-if="(tab==='inbound'||tab==='outbound')&&row.items?.length" class="item-summary">{{ row.items.map((item:Row)=>`${item.sku||item.product_name} × ${item.quantity}`).join('；') }}</small></div>
            <div class="warehouse-value"><strong>{{ value(row) }}</strong><IonIcon v-if="canWrite && ['warehouses','products'].includes(tab)" :icon="arrowForwardOutline" /></div>
            <div v-if="tab==='stocks'" class="stock-detail">实际 {{ row.quantity??0 }} · 锁定 {{ row.locked_quantity??0 }} · 可用 {{ row.available_quantity??0 }} · 预警 {{ row.warning_quantity??0 }}</div>
            <div v-if="tab==='inbound'&&canWrite&&row.status==='completed'" class="order-actions" @click.stop><button @click="openRow(row)">纠正</button><button class="danger" @click="cancelInbound(row)">撤销</button></div>
            <div v-if="tab === 'outbound' && canWrite && !['shipped','cancelled'].includes(row.status)" class="order-actions" @click.stop>
              <button v-if="nextStatus[row.status]" @click="updateOutbound(row, nextStatus[row.status])">{{ statusLabels[nextStatus[row.status]] }}</button>
              <button class="danger" @click="updateOutbound(row, 'cancelled')">取消</button>
            </div>
          </article>
          <div v-if="!rows.length" class="empty-state">暂无{{ labels[tab] }}数据</div>
        </section>
      </main>
    </IonContent>
  </IonPage>
</template>

<style scoped>
.warehouse-tabs{display:flex;gap:7px;overflow-x:auto;margin:14px 0 10px;padding-bottom:2px}.warehouse-tabs button{flex:none;border:1px solid var(--app-line);border-radius:999px;padding:8px 14px;color:var(--app-muted);background:var(--app-card)}.warehouse-tabs .active{color:#fff;border-color:#f97316;background:#f97316}.list-toolbar{display:flex;justify-content:space-between;align-items:center;margin:12px 2px 8px}.list-toolbar button{display:flex;align-items:center;gap:3px;padding:8px 12px;border:0;border-radius:10px;color:#fff;background:#f97316}.warehouse-list{border-radius:16px}.warehouse-row{display:grid;grid-template-columns:40px 1fr auto;gap:11px;align-items:center;padding:13px 12px;border-bottom:1px solid var(--app-line)}.warehouse-row:last-child{border-bottom:0}.warehouse-icon{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;color:#f97316;background:#fff0e6;font-weight:700}.warehouse-main{min-width:0}.warehouse-main h3,.warehouse-main p{margin:0}.warehouse-main h3{font-size:15px}.warehouse-main p{margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--app-muted);font-size:12px}.warehouse-main small{display:block;margin-top:4px;color:var(--app-muted);font-size:10px}.warehouse-value{display:flex;align-items:center;gap:4px;color:#f97316}.warehouse-value strong{max-width:90px;text-align:right;font-size:13px}.order-actions{grid-column:2/4;display:flex;gap:8px}.order-actions button{padding:7px 11px;border:0;border-radius:9px;color:#fff;background:#f97316}.order-actions .danger{color:#ef4444;background:#fee2e2}.ion-palette-dark .warehouse-icon{background:#3b2416}.ion-palette-dark .order-actions .danger{background:#451a1a}
.warehouse-icon img{width:100%;height:100%;object-fit:cover;border-radius:12px}.item-summary{max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#475569!important}
.stock-detail{grid-column:2/4;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding-top:3px;color:var(--app-muted);font-size:11px;line-height:1.45;white-space:nowrap}.warehouse-filters{display:flex;gap:8px;margin-top:5px}.warehouse-filters select{max-width:100%;padding:8px 10px;border:1px solid var(--app-line);border-radius:9px;color:var(--app-text);background:var(--app-card)}
@media(max-width:380px){.warehouse-row{grid-template-columns:38px minmax(0,1fr) auto;gap:9px}.stock-detail{grid-template-columns:1fr 1fr;white-space:normal}.warehouse-value strong{max-width:64px}.warehouse-page{padding-inline:8px}}
</style>
